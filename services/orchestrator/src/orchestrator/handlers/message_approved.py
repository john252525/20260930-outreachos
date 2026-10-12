"""Handle message.approved (observability; sender-email auto-subscribes)."""

from typing import Any

import structlog

from contracts.base import EventEnvelope
from orchestrator.handlers.base import StepHandler

logger = structlog.get_logger()


class MessageApprovedHandler(StepHandler):
    event_type = "message.approved"
    step_name = "message_approved"

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        logger.info(
            "flow_message_approved",
            message_id=str(getattr(envelope.payload, "message_id", "")),
            tenant_id=str(envelope.tenant_id),
        )
