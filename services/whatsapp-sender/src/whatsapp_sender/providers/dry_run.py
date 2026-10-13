"""Dry-run provider — never touches the network."""

import structlog

from whatsapp_sender.providers.base import SendResult, WhatsAppProvider

logger = structlog.get_logger()


class DryRunProvider(WhatsAppProvider):
    name = "dry-run"

    async def send_text_message(self, *, to_phone: str, text: str) -> SendResult:
        logger.info("whatsapp_dry_run_text", to=to_phone)
        return SendResult(success=True, message_id=f"dry-run-{to_phone}")

    async def send_template_message(
        self, *, to_phone: str, template_name: str, language: str, variables: list[str]
    ) -> SendResult:
        logger.info("whatsapp_dry_run_template", to=to_phone, template=template_name)
        return SendResult(success=True, message_id=f"dry-run-tpl-{to_phone}")
