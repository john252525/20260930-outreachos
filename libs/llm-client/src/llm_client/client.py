"""HTTP client for the llm-gateway service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class LLMClientError(Exception):
    """Raised when the llm-gateway returns an error."""


class LLMClient:
    """Thin async wrapper around the llm-gateway HTTP API."""

    def __init__(self, base_url: str, *, timeout: float = 180.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    async def complete(
        self,
        *,
        tenant_id: UUID,
        task_type: str,
        user: str,
        system: str | None = None,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
        use_cache: bool = True,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "X-Tenant-ID": str(tenant_id),
            "Content-Type": "application/json",
        }
        if trace_id:
            headers["X-Trace-Id"] = trace_id

        payload = {
            "task_type": task_type,
            "system": system,
            "user": user,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "json_mode": json_mode,
            "use_cache": use_cache,
        }
        response = await self._client.post("/v1/complete", json=payload, headers=headers)
        if response.status_code >= 400:
            raise LLMClientError(f"llm-gateway error {response.status_code}: {response.text}")
        return dict(response.json())

    async def close(self) -> None:
        await self._client.aclose()
