"""Thin HTTP proxy to the other services."""

from typing import Any

import httpx


class ServiceProxy:
    """Calls backend services, injecting the tenant header when needed."""

    def __init__(self, urls: dict[str, str], *, timeout: float = 20.0) -> None:
        self._urls = urls
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5.0))

    def url_for(self, service: str) -> str:
        if service not in self._urls:
            raise KeyError(f"Unknown service: {service}")
        return self._urls[service]

    async def get(
        self,
        service: str,
        path: str,
        *,
        tenant_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        resp = await self._client.get(
            f"{self._urls[service]}{path}", headers=headers, params=params or {}
        )
        try:
            body: Any = resp.json()
        except Exception:
            body = resp.text
        return resp.status_code, body

    async def post(
        self,
        service: str,
        path: str,
        *,
        tenant_id: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        resp = await self._client.post(f"{self._urls[service]}{path}", headers=headers, json=json)
        try:
            body: Any = resp.json()
        except Exception:
            body = resp.text
        return resp.status_code, body

    async def health(self, service: str) -> dict[str, Any]:
        try:
            resp = await self._client.get(f"{self._urls[service]}/healthz", timeout=3.0)
            return {"service": service, "ok": resp.status_code == 200, "status": resp.status_code}
        except Exception as e:
            return {"service": service, "ok": False, "error": str(e)}

    async def close(self) -> None:
        await self._client.aclose()
