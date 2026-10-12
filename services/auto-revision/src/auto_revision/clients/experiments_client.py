"""HTTP client to experiments-service."""

from typing import Any

import httpx


class ExperimentsClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(60.0, connect=5.0)
        )

    async def create_experiment(
        self,
        *,
        tenant_id: str,
        data: dict[str, Any],
        trace_id: str = "",
        idempotency_key: str,
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/experiments",
            json=data,
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
                "Idempotency-Key": idempotency_key,
            },
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def start_experiment(
        self, experiment_id: str, *, tenant_id: str, trace_id: str = "", idempotency_key: str
    ) -> dict[str, Any]:
        resp = await self._client.post(
            f"/experiments/{experiment_id}/start",
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
