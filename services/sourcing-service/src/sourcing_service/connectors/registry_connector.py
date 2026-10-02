"""Registry connector (RU company registries) with a provider abstraction."""

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

from sourcing_service.connectors.base import (
    Connector,
    ConnectorResult,
    RawCandidate,
    SearchCriteria,
)

logger = structlog.get_logger()


class RegistryProvider(ABC):
    name: str

    @abstractmethod
    async def search_by_query(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def search_by_inn(self, inn: str) -> dict[str, Any] | None: ...

    async def close(self) -> None:
        return None


class DaDataProvider(RegistryProvider):
    """DaData party search. Docs: https://dadata.ru/api/find-party/"""

    name = "dadata"

    def __init__(self, api_key: str, secret_key: str) -> None:
        self._api_key = api_key
        self._secret = secret_key
        self._client = httpx.AsyncClient(
            base_url="https://suggestions.dadata.ru/suggestions/api/4_1/rs",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Token {api_key}",
                "X-Secret": secret_key,
            },
            timeout=httpx.Timeout(20.0, connect=5.0),
        )

    @property
    def is_available(self) -> bool:
        return bool(self._api_key and self._secret)

    async def search_by_query(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        resp = await self._client.post("/findById/party", json={"query": query, "count": limit})
        resp.raise_for_status()
        return list(resp.json().get("suggestions", []))

    async def search_by_inn(self, inn: str) -> dict[str, Any] | None:
        results = await self.search_by_query(inn, limit=1)
        return results[0] if results else None

    async def close(self) -> None:
        await self._client.aclose()


class RegistryConnector(Connector):
    """Company search in RU registries via a provider (default: DaData)."""

    name = "registry"

    def __init__(self, provider: RegistryProvider, *, cost_per_call_usd: float = 0.00005) -> None:
        super().__init__(rate_limit_per_sec=5.0)
        self._provider = provider
        self._cost = cost_per_call_usd

    @property
    def is_available(self) -> bool:
        return bool(getattr(self._provider, "is_available", True))

    @property
    def cost_per_call_usd(self) -> float:
        return self._cost

    async def search(self, criteria: SearchCriteria) -> ConnectorResult:
        started = time.monotonic()
        candidates: list[RawCandidate] = []
        errors: list[str] = []
        queries = criteria.keywords[:3]
        for q in queries:
            try:
                results = await self._provider.search_by_query(q, limit=criteria.limit)
                for item in results:
                    data = item.get("data", {})
                    name = data.get("name", {}).get("short_with_opf") or data.get("name", {}).get(
                        "full_with_opf"
                    )
                    inn = data.get("inn")
                    ogrn = data.get("ogrn")
                    address = data.get("address", {}).get("value")
                    management = data.get("management") or {}
                    okved = data.get("okved")
                    employee_count = data.get("employee_count")
                    status = data.get("state", {}).get("status")
                    if not name:
                        continue
                    if status and status != "ACTIVE":
                        continue
                    candidates.append(
                        RawCandidate(
                            source=self.name,
                            source_url=None,
                            title=name,
                            snippet=f"ИНН {inn}, {address or ''}".strip(", "),
                            domain=None,
                            raw_payload={
                                "name": name,
                                "inn": inn,
                                "ogrn": ogrn,
                                "address": address,
                                "manager_name": management.get("name"),
                                "manager_post": management.get("post"),
                                "okved": okved,
                                "employee_count": employee_count,
                                "status": status,
                                "source": self._provider.name,
                            },
                        )
                    )
            except Exception as e:
                logger.warning("registry_query_failed", query=q, error=str(e))
                errors.append(f"{q}: {e}")
        duration_ms = int((time.monotonic() - started) * 1000)
        return ConnectorResult(
            source=self.name,
            candidates=candidates,
            cost_usd=self._cost * len(queries),
            error="; ".join(errors) if errors else None,
            duration_ms=duration_ms,
        )

    async def close(self) -> None:
        await self._provider.close()
