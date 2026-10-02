"""Enricher connector: email/phone enrichment via a provider."""

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


class EnricherProvider(ABC):
    name: str

    @abstractmethod
    async def find_email(
        self, *, domain: str, first_name: str | None, last_name: str | None
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    async def domain_emails(self, *, domain: str, limit: int = 10) -> list[dict[str, Any]]: ...

    async def close(self) -> None:
        return None


class HunterProvider(EnricherProvider):
    """Hunter.io email finder. Docs: https://hunter.io/api-documentation"""

    name = "hunter"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url="https://api.hunter.io/v2", timeout=httpx.Timeout(20.0, connect=5.0)
        )

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def find_email(
        self, *, domain: str, first_name: str | None, last_name: str | None
    ) -> dict[str, Any] | None:
        if not first_name or not last_name:
            return None
        resp = await self._client.get(
            "/email-finder",
            params={
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name,
                "api_key": self._api_key,
            },
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json().get("data")
        return dict(data) if data else None

    async def domain_emails(self, *, domain: str, limit: int = 10) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/domain-search",
            params={"domain": domain, "limit": limit, "api_key": self._api_key},
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return list(resp.json().get("data", {}).get("emails", []))

    async def close(self) -> None:
        await self._client.aclose()


class EnricherConnector(Connector):
    """Enriches contacts with email/phone. Works on ``criteria.extra['contacts']``."""

    name = "enricher"

    def __init__(self, provider: EnricherProvider, *, cost_per_email_usd: float = 0.02) -> None:
        super().__init__(rate_limit_per_sec=3.0)
        self._provider = provider
        self._cost = cost_per_email_usd

    @property
    def is_available(self) -> bool:
        return bool(getattr(self._provider, "is_available", True))

    async def search(self, criteria: SearchCriteria) -> ConnectorResult:
        started = time.monotonic()
        contacts = criteria.extra.get("contacts", [])
        candidates: list[RawCandidate] = []
        cost = 0.0
        for c in contacts:
            domain = c.get("company_domain")
            if not domain:
                continue
            try:
                found = await self._provider.find_email(
                    domain=domain,
                    first_name=c.get("first_name"),
                    last_name=c.get("last_name"),
                )
                if found and found.get("email"):
                    cost += self._cost
                    candidates.append(
                        RawCandidate(
                            source=self.name,
                            source_url=None,
                            title=c.get("full_name"),
                            snippet=found.get("email"),
                            domain=domain,
                            raw_payload={
                                "contact_full_name": c.get("full_name"),
                                "email": found.get("email"),
                                "confidence": found.get("confidence", 50) / 100.0,
                                "source": self._provider.name,
                            },
                        )
                    )
            except Exception as e:
                logger.warning("enrich_failed", domain=domain, error=str(e))
        duration_ms = int((time.monotonic() - started) * 1000)
        return ConnectorResult(
            source=self.name, candidates=candidates, cost_usd=cost, duration_ms=duration_ms
        )

    async def close(self) -> None:
        await self._provider.close()
