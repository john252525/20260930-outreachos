"""Serper (Google Search API) connector."""

import asyncio
import time
from typing import Any

import httpx
import structlog
import tldextract
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sourcing_service.connectors.base import (
    Connector,
    ConnectorResult,
    RawCandidate,
    SearchCriteria,
)
from sourcing_service.connectors.exceptions import (
    ConnectorAuthError,
    ConnectorRateLimitError,
    ConnectorUnavailableError,
)

logger = structlog.get_logger()


class _RateLimiter:
    """Simple rate limiter: no more than N requests per second."""

    def __init__(self, per_sec: float) -> None:
        self._interval = 1.0 / per_sec if per_sec > 0 else 0.0
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self._interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class SerperConnector(Connector):
    """Google Search via Serper.dev API."""

    name = "serper"
    COST_PER_CALL_USD = 0.0003

    def __init__(self, *, api_key: str, base_url: str, rate_limit_per_sec: float = 5.0) -> None:
        super().__init__(rate_limit_per_sec=rate_limit_per_sec)
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
        self._limiter = _RateLimiter(rate_limit_per_sec)

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def cost_per_call_usd(self) -> float:
        return self.COST_PER_CALL_USD

    async def search(self, criteria: SearchCriteria) -> ConnectorResult:
        if not self.is_available:
            raise ConnectorUnavailableError("Serper API key not set")
        started = time.monotonic()
        candidates: list[RawCandidate] = []
        seen_domains: set[str] = set()
        errors: list[str] = []

        for query in criteria.keywords[:5]:
            try:
                await self._limiter.acquire()
                results = await self._search_one(query, criteria)
                for item in results:
                    domain = self._extract_domain(item.get("link", ""))
                    if not domain or domain in seen_domains:
                        continue
                    if domain in criteria.domain_blacklist:
                        continue
                    if criteria.domain_whitelist and domain not in criteria.domain_whitelist:
                        continue
                    seen_domains.add(domain)
                    candidates.append(
                        RawCandidate(
                            source=self.name,
                            source_url=item.get("link"),
                            title=item.get("title"),
                            snippet=item.get("snippet"),
                            domain=domain,
                            raw_payload=item,
                        )
                    )
                    if len(candidates) >= criteria.limit:
                        break
                if len(candidates) >= criteria.limit:
                    break
            except Exception as e:
                logger.warning("serper_query_failed", query=query, error=str(e))
                errors.append(f"{query}: {e}")

        duration_ms = int((time.monotonic() - started) * 1000)
        cost = self.COST_PER_CALL_USD * min(len(criteria.keywords), 5)
        return ConnectorResult(
            source=self.name,
            candidates=candidates,
            cost_usd=cost,
            error="; ".join(errors) if errors else None,
            duration_ms=duration_ms,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _search_one(self, query: str, criteria: SearchCriteria) -> list[dict[str, Any]]:
        gl = criteria.geo[0].lower() if criteria.geo else "ru"
        hl = criteria.language
        payload = {"q": query, "gl": gl, "hl": hl, "num": min(criteria.limit, 100)}
        resp = await self._client.post("/search", json=payload)
        if resp.status_code in (401, 403):
            raise ConnectorAuthError(f"Serper auth failed: {resp.status_code}")
        if resp.status_code == 429:
            raise ConnectorRateLimitError("Serper rate limit")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return list(data.get("organic", []))

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        if not url:
            return None
        ext = tldextract.extract(url)
        if not ext.domain or not ext.suffix:
            return None
        return f"{ext.domain}.{ext.suffix}".lower()

    async def close(self) -> None:
        await self._client.aclose()
