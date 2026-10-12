"""Telegram Bot API client (abstracted; dry-run friendly).

Uses raw HTTP calls to the Bot API so we avoid pulling a heavyweight framework.
"""

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

API_BASE = "https://api.telegram.org"


class BotClient:
    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.AsyncClient(base_url=f"{API_BASE}/bot{token}", timeout=30.0)

    async def send(self, *, chat_id: str, text: str) -> dict[str, Any]:
        try:
            resp = await self._client.post("/sendMessage", json={"chat_id": chat_id, "text": text})
            data = resp.json()
            if resp.status_code == 429:
                retry_after = (data.get("parameters") or {}).get("retry_after", 60)
                return {
                    "success": False,
                    "flood_wait_seconds": int(retry_after),
                    "error": "flood_wait",
                }
            if not data.get("ok"):
                desc = data.get("description", "unknown")
                err = "blocked_by_user" if "blocked" in desc.lower() else desc
                return {"success": False, "error": err}
            return {"success": True, "message_id": data["result"]["message_id"]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_me(self) -> dict[str, Any]:
        resp = await self._client.get("/getMe")
        return dict(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
