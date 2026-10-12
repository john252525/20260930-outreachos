"""HTTP client to composer-service (template overrides)."""

from typing import Any

import httpx


class ComposerClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(60.0, connect=5.0)
        )

    async def create_template_override(
        self,
        *,
        tenant_id: str,
        template_id: str,
        base_version: str,
        override_version: str,
        system_prompt: str,
        user_prompt_template: str,
        source_revision_id: str | None,
        trace_id: str = "",
        idempotency_key: str,
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/templates/overrides",
            json={
                "template_id": template_id,
                "base_version": base_version,
                "override_version": override_version,
                "system_prompt": system_prompt,
                "user_prompt_template": user_prompt_template,
                "source_revision_id": source_revision_id,
                "is_active": True,
            },
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Trace-Id": trace_id,
                "Idempotency-Key": idempotency_key,
            },
        )
        resp.raise_for_status()
        return dict(resp.json())

    async def list_overrides(self, *, tenant_id: str, trace_id: str = "") -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/templates/overrides",
            headers={"X-Tenant-ID": tenant_id, "X-Trace-Id": trace_id},
        )
        resp.raise_for_status()
        return list(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
