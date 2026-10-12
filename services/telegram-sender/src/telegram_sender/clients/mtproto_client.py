"""MTProto (Telethon) client wrapper.

Imported lazily so that dry-run / Bot-only deployments don't pay the import cost.
"""

from contextlib import suppress
from typing import Any

import structlog

logger = structlog.get_logger()


class MTProtoClient:
    def __init__(self, *, api_id: int, api_hash: str, session_string: str) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_string = session_string
        self._client: Any = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        from telethon import TelegramClient  # local import (heavy)
        from telethon.sessions import StringSession

        self._client = TelegramClient(
            StringSession(self._session_string), self._api_id, self._api_hash
        )
        await self._client.connect()

    async def send(self, *, peer: str, text: str) -> dict[str, Any]:
        await self.connect()
        try:
            from telethon.errors import FloodWaitError, UserPrivacyRestrictedError

            msg = await self._client.send_message(peer, text, link_preview=False)
            return {"success": True, "message_id": msg.id}
        except FloodWaitError as e:
            return {"success": False, "flood_wait_seconds": e.seconds, "error": "flood_wait"}
        except UserPrivacyRestrictedError:
            return {"success": False, "error": "privacy_restricted"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self) -> None:
        if self._client is not None:
            with suppress(Exception):
                await self._client.disconnect()
            self._client = None
