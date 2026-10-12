"""Handle message.drafted (observability only; review-queue auto-subscribes)."""

from typing import Any

import structlog

from contracts.base import EventEnvelope
from orchestrator.handlers.base import StepHandler

logger = structlog.get_logger()


class MessageDraftedHandler(StepHandler):
    event_type = "message.drafted"
    step_name = "message_drafted"

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        message = getattr(envelope.payload, "message", None)
        if message is None:
            return
        logger.info(
            "flow_message_drafted",
            message_id=str(message.id),
            contact_id=str(message.contact_id),
            tenant_id=str(envelope.tenant_id),
        )
