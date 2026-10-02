"""HTTP client to composer-service."""

from typing import Any
from uuid import UUID

import httpx
import structlog

logger = structlog.get_logger()


class ComposerClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    async def get_message(
        self, message_id: UUID, *, tenant_id: str, trace_id: str = ""
    ) -> dict[str, Any] | None:
        resp = await self._client.get(
            f"/messages/{message_id}",
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return dict(resp.json())

    async def update_message(
        self,
        message_id: UUID,
        *,
        tenant_id: str,
        payload: dict[str, Any],
        trace_id: str = "",
        idempotency_key: str,
    ) -> dict[str, Any]:
        resp = await self._client.patch(
            f"/messages/{message_id}",
            json=payload,
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
