"""Dry-run LinkedIn client — never touches the network."""

import structlog

from linkedin_sender.clients.base import SendResult

logger = structlog.get_logger()


class DryRunClient:
    def __init__(self, *, account_email: str) -> None:
        self._account_email = account_email

    async def send_message(self, *, handle: str, text: str) -> SendResult:
        logger.info("linkedin_dry_run", handle=handle, account=self._account_email)
        return SendResult(success=True, message_id=f"dry-run-{handle}")

    async def close(self) -> None:
        return None
