"""Gupshup WhatsApp provider."""

import json

import httpx
import structlog

from whatsapp_sender.providers.base import SendResult, WhatsAppProvider

logger = structlog.get_logger()


class GupshupProvider(WhatsAppProvider):
    name = "gupshup"

    def __init__(self, api_key: str, app_name: str) -> None:
        self._app_name = app_name
        self._client = httpx.AsyncClient(
            base_url="https://api.gupshup.io/wa/api/v1",
            headers={"apikey": api_key},
            timeout=httpx.Timeout(30.0),
        )

    async def send_text_message(self, *, to_phone: str, text: str) -> SendResult:
        payload = {
            "channel": "whatsapp",
            "source": self._app_name,
            "destination": to_phone,
            "message": json.dumps({"type": "text", "text": text}),
        }
        try:
            resp = await self._client.post("/msg", data=payload)
            resp.raise_for_status()
            data = resp.json()
            return SendResult(success=True, message_id=str(data.get("messageId")))
        except Exception as e:
            logger.warning("gupshup_send_failed", error=str(e))
            return SendResult(success=False, error=str(e))

    async def send_template_message(
        self, *, to_phone: str, template_name: str, language: str, variables: list[str]
    ) -> SendResult:
        payload = {
            "channel": "whatsapp",
            "source": self._app_name,
            "destination": to_phone,
            "src.name": self._app_name,
            "template": json.dumps({"id": template_name, "params": variables}),
        }
        try:
            resp = await self._client.post("/msg", data=payload)
            resp.raise_for_status()
            data = resp.json()
            return SendResult(success=True, message_id=str(data.get("messageId")))
        except Exception as e:
            logger.warning("gupshup_template_failed", error=str(e))
            return SendResult(success=False, error=str(e))

    async def close(self) -> None:
        await self._client.aclose()
