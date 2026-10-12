"""HTTP client to icp-service."""

from typing import Any

import httpx


class ICPClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(300.0, connect=5.0)
        )

    async def generate_icp(
        self, *, tenant_id: str, brief_id: str, trace_id: str = ""
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/icps",
            json={"brief_id": brief_id},
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def get_icp(self, icp_id: str, *, tenant_id: str, trace_id: str = "") -> dict[str, Any]:
        resp = await self._client.get(
            f"/icps/{icp_id}",
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
