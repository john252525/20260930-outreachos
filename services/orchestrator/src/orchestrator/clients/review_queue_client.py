"""HTTP client to review-queue."""

from typing import Any

import httpx


class ReviewQueueClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(60.0, connect=5.0)
        )

    async def list_items(
        self,
        *,
        tenant_id: str,
        status: str | None = "pending",
        limit: int = 50,
        trace_id: str = "",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        resp = await self._client.get(
            "/review-items",
            params=params,
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return list(resp.json())

    async def close(self) -> None:
        await self._client.aclose()


class RevisionClient:
    """HTTP client to auto-revision service (5B)."""

    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(600.0, connect=5.0)
        )

    async def propose(
        self,
        *,
        tenant_id: str,
        trigger_type: str,
        trigger_context: dict[str, Any],
        trace_id: str = "",
        idempotency_key: str,
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/revisions/propose",
            json={"trigger_type": trigger_type, "trigger_context": trigger_context},
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
