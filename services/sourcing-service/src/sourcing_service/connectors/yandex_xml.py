"""Yandex XML Search API connector."""

import time
from typing import Any
from xml.etree import ElementTree as ET

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


class YandexXMLConnector(Connector):
    """Yandex XML Search API."""

    name = "yandex_xml"
    ENDPOINT = "https://yandex.com/search/xml"
    COST_PER_CALL_USD = 0.0006

    def __init__(self, *, user: str, key: str, rate_limit_per_sec: float = 1.0) -> None:
        super().__init__(rate_limit_per_sec=rate_limit_per_sec)
        self._user = user
        self._key = key
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))

    @property
    def is_available(self) -> bool:
        return bool(self._user and self._key)

    @property
    def cost_per_call_usd(self) -> float:
        return self.COST_PER_CALL_USD

    async def search(self, criteria: SearchCriteria) -> ConnectorResult:
        if not self.is_available:
            raise ConnectorUnavailableError("Yandex XML credentials not set")
        started = time.monotonic()
        candidates: list[RawCandidate] = []
        seen_domains: set[str] = set()
        errors: list[str] = []

        for query in criteria.keywords[:5]:
            try:
                results = await self._search_one(query, criteria)
                for item in results:
                    domain = self._extract_domain(item.get("url", ""))
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
                            source_url=item.get("url"),
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
                logger.warning("yandex_xml_query_failed", query=query, error=str(e))
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
        retry=retry_if_exception_type((httpx.TransportError,)),
        reraise=True,
    )
    async def _search_one(self, query: str, criteria: SearchCriteria) -> list[dict[str, Any]]:
        params = {
            "user": self._user,
            "key": self._key,
            "query": query,
            "lr": self._geo_to_yandex_region(criteria.geo),
            "l10n": criteria.language,
            "sortby": "rlv",
            "filter": "strict",
            "groupby": "attr=d.mode=deep.groups-on-page=10.docs-in-group=1",
            "maxpassages": "3",
            "page": "0",
        }
        resp = await self._client.get(self.ENDPOINT, params=params)
        if resp.status_code in (401, 403):
            raise ConnectorAuthError(f"Yandex XML auth failed: {resp.status_code}")
        if resp.status_code == 429:
            raise ConnectorRateLimitError("Yandex XML rate limit")
        resp.raise_for_status()
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            raise ConnectorRateLimitError(f"Yandex XML parse error: {e}") from e

        error_el = root.find(".//error")
        if error_el is not None:
            code = error_el.get("code", "")
            if code in ("15", "32", "33"):
                raise ConnectorRateLimitError(f"Yandex XML error: {code}")
            raise ConnectorAuthError(f"Yandex XML error: {code} {error_el.text}")

        results: list[dict[str, Any]] = []
        for doc in root.findall(".//doc"):
            url_el = doc.find("url")
            title_el = doc.find("title")
            passages = doc.findall(".//passage")
            snippet = " ".join(p.text or "" for p in passages if p.text)
            results.append(
                {
                    "url": url_el.text if url_el is not None else None,
                    "title": title_el.text if title_el is not None else None,
                    "snippet": snippet,
                }
            )
        return results

    @staticmethod
    def _geo_to_yandex_region(geos: list[str]) -> str:
        if not geos:
            return "225"
        mapping = {"RU": "225", "KZ": "159", "BY": "149", "UA": "187"}
        return mapping.get(geos[0].upper(), "225")

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
