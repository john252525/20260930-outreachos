"""HTTP client to tenant-service (create tenant + settings)."""

from typing import Any

import httpx


class TenantClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    async def create_tenant(self, *, name: str, slug: str, idempotency_key: str) -> dict[str, Any]:
        resp = await self._client.post(
            "/tenants",
            json={"name": name, "slug": slug},
            headers={"Idempotency-Key": idempotency_key},
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
