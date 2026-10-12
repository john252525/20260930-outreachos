"""HTTP client to tenant-service (settings + opt-in)."""

import contextlib
import json
from typing import Any

import httpx


class TenantClient:
    def __init__(self, base_url: str, redis: Any) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )
        self._redis = redis

    async def get_settings(self, tenant_id: str) -> dict[str, Any]:
        cache_key = f"tenant:settings:{tenant_id}"
        with contextlib.suppress(Exception):
            cached = await self._redis.get(cache_key)
            if cached:
                return dict(json.loads(cached))

        resp = await self._client.get(
            f"/tenants/{tenant_id}/settings", headers={"X-Tenant-ID": tenant_id}
        )
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        settings: dict[str, Any] = dict(resp.json())
        with contextlib.suppress(Exception):
            await self._redis.setex(cache_key, 300, json.dumps(settings))
        return settings

    async def close(self) -> None:
        await self._client.aclose()
