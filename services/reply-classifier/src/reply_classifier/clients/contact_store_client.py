"""HTTP client to contact-store."""

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx


class ContactStoreClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    async def update_contact_status(self, contact_id: UUID, *, tenant_id: str, status: str) -> None:
        resp = await self._client.post(
            f"/contacts/{contact_id}/status",
            json={"status": status},
            headers={
                "X-Tenant-ID": tenant_id,
                "Idempotency-Key": f"reply-status-{contact_id}-{status}",
            },
        )
        resp.raise_for_status()

    async def update_contact_outreach_history(
        self,
        contact_id: UUID,
        *,
        tenant_id: str,
        replied_positive: bool | None = None,
        last_reply_at: datetime | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if replied_positive is not None:
            body["replied_positive"] = replied_positive
        if last_reply_at is not None:
            body["last_reply_at"] = last_reply_at.isoformat()
        stamp = int(last_reply_at.timestamp()) if last_reply_at else 0
        resp = await self._client.patch(
            f"/contacts/{contact_id}/outreach-history",
            json=body,
            headers={
                "X-Tenant-ID": tenant_id,
                "Idempotency-Key": f"reply-history-{contact_id}-{stamp}",
            },
        )
        resp.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
