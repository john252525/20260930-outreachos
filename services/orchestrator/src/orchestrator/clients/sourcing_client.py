"""HTTP client to sourcing-service."""

from typing import Any

import httpx


class SourcingClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(600.0, connect=5.0)
        )

    async def start_search(
        self,
        *,
        tenant_id: str,
        icp_id: str,
        segment_id: str,
        sources: list[str] | None,
        limit_per_source: int | None,
        trace_id: str = "",
        idempotency_key: str,
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/searches",
            json={
                "icp_id": icp_id,
                "segment_id": segment_id,
                "sources": sources,
                "limit_per_source": limit_per_source,
            },
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
                "Idempotency-Key": idempotency_key,
            },
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
