"""HTTP client to analytics-service."""

from typing import Any

import httpx


class AnalyticsClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    async def get_overview(
        self, *, tenant_id: str, from_date: str, to_date: str, trace_id: str = ""
    ) -> dict[str, Any]:
        resp = await self._client.get(
            "/analytics/overview",
            params={"from_date": from_date, "to_date": to_date},
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
