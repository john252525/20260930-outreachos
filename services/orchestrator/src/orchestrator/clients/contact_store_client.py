"""HTTP client to contact-store."""

from typing import Any
from uuid import UUID

import httpx


class ContactStoreClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(60.0, connect=5.0)
        )

    async def get_contact(
        self, contact_id: UUID, *, tenant_id: str, trace_id: str = ""
    ) -> dict[str, Any] | None:
        resp = await self._client.get(
            f"/contacts/{contact_id}",
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return dict(resp.json())

    async def list_contacts(
        self,
        *,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
        trace_id: str = "",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        resp = await self._client.get(
            "/contacts",
            params=params,
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return list(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
