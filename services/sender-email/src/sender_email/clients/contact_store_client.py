"""HTTP client to contact-store (stop-list check)."""

from typing import Any

import httpx


class ContactStoreClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(30.0, connect=5.0)
        )

    async def check_stoplist(
        self, *, tenant_id: str, email: str | None = None
    ) -> tuple[bool, str | None]:
        resp = await self._client.get(
            "/stoplist",
            headers={"X-Tenant-ID": tenant_id},
        )
        if resp.status_code != 200:
            return False, None
        entries: list[dict[str, Any]] = resp.json()
        for e in entries:
            if e.get("kind") == "email" and email and e.get("value") == email:
                return True, e.get("reason")
        return False, None

    async def close(self) -> None:
        await self._client.aclose()
