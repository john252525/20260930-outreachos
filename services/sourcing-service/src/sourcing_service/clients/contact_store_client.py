"""HTTP client to contact-store."""

from typing import Any

import httpx
import structlog

from common.errors import AppError

logger = structlog.get_logger()


class ContactStoreClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(60.0, connect=5.0)
        )

    async def upsert_company(
        self,
        *,
        tenant_id: str,
        payload: dict[str, Any],
        trace_id: str = "",
        idempotency_key: str,
    ) -> tuple[dict[str, Any] | None, str]:
        resp = await self._client.post(
            "/companies",
            json={"payload": payload},
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
                "Idempotency-Key": idempotency_key,
            },
        )
        if resp.status_code not in (200, 201):
            raise AppError(
                f"contact-store upsert failed: {resp.status_code} {resp.text}",
                code="contact_store_error",
                status_code=502,
            )
        data = resp.json()
        return data.get("company"), data.get("action", "created")

    async def upsert_contact(
        self,
        *,
        tenant_id: str,
        payload: dict[str, Any],
        trace_id: str = "",
        idempotency_key: str,
    ) -> tuple[dict[str, Any] | None, str]:
        resp = await self._client.post(
            "/contacts",
            json={"payload": payload},
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
                "Idempotency-Key": idempotency_key,
            },
        )
        if resp.status_code == 409:
            data = resp.json()
            return None, f"blocked:{data.get('reason', 'unknown')}"
        if resp.status_code not in (200, 201):
            raise AppError(
                f"contact-store upsert failed: {resp.status_code}",
                code="contact_store_error",
                status_code=502,
            )
        data = resp.json()
        return data.get("contact"), data.get("action", "created")

    async def close(self) -> None:
        await self._client.aclose()
