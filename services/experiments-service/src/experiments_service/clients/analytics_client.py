"""HTTP client to analytics-service."""

from typing import Any
from uuid import UUID

import httpx


class AnalyticsClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    async def get_segments(
        self, *, tenant_id: str, from_date: str, to_date: str, trace_id: str = ""
    ) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/analytics/segments",
            params={"from_date": from_date, "to_date": to_date},
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return list(resp.json())

    async def get_funnel(self, *, tenant_id: str, trace_id: str = "") -> dict[str, Any]:
        resp = await self._client.get(
            "/analytics/funnel",
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def get_experiment_variants_for(
        self, *, tenant_id: str, experiment_id: UUID, trace_id: str = ""
    ) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/analytics/experiment-variants",
            params={"experiment_id": str(experiment_id)},
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return list(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
