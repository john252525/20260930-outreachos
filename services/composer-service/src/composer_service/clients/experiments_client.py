"""HTTP client to experiments-service."""

from typing import Any
from uuid import UUID

import httpx


class ExperimentsClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    async def assign_variant(
        self,
        *,
        experiment_id: UUID,
        contact_id: UUID,
        tenant_id: str,
        trace_id: str = "",
        idempotency_key: str,
    ) -> dict[str, Any]:
        resp = await self._client.post(
            f"/experiments/{experiment_id}/assign",
            json={"contact_id": str(contact_id)},
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
                "Idempotency-Key": idempotency_key,
            },
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def get_experiment(
        self, experiment_id: UUID, *, tenant_id: str, trace_id: str = ""
    ) -> dict[str, Any]:
        resp = await self._client.get(
            f"/experiments/{experiment_id}",
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
