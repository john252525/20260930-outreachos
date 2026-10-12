"""Handle analytics.alert → trigger auto-revision (5B)."""

from typing import Any

import structlog

from contracts.base import EventEnvelope
from orchestrator.clients.review_queue_client import RevisionClient
from orchestrator.config import Settings
from orchestrator.handlers.base import StepHandler

logger = structlog.get_logger()


class AnalyticsAlertHandler(StepHandler):
    event_type = "analytics.alert"
    step_name = "auto_revision"

    def __init__(
        self,
        revision_client: RevisionClient,
        settings: Settings,
    ) -> None:
        self._revision = revision_client
        self._settings = settings

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        if not self._settings.auto_revision_enabled:
            return
        alert_type = getattr(envelope.payload, "alert_type", None)
        if alert_type not in ("low_reply_rate", "low_positive_reply_rate"):
            return

        try:
            revision = await self._revision.propose(
                tenant_id=str(envelope.tenant_id),
                trigger_type=alert_type,
                trigger_context={
                    "metrics": {
                        "value": getattr(envelope.payload, "value", 0.0),
                        "threshold": getattr(envelope.payload, "threshold", 0.0),
                    },
                    "window_days": 30,
                },
                trace_id=envelope.trace_id,
                idempotency_key=f"orchestrator:revision:{envelope.event_id}",
            )
            logger.info("revision_proposed", revision_id=revision.get("id"))
        except Exception as e:
            logger.warning("revision_propose_failed", error=str(e))
