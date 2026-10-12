"""Handle message.sent → advance flow progress, complete if done."""

from datetime import UTC, datetime
from typing import Any

import structlog

from contracts.base import EventEnvelope
from db.rls import set_tenant_context
from db.session import async_session_factory
from nats_client.publisher import Publisher
from orchestrator.clients.composer_client import ComposerClient
from orchestrator.config import Settings
from orchestrator.events import emit_flow_completed, emit_flow_step_completed
from orchestrator.handlers.base import StepHandler, complete_step, start_step
from orchestrator.metrics import FLOW_STEPS_TOTAL
from orchestrator.repository import FlowRepository

logger = structlog.get_logger()


class MessageSentHandler(StepHandler):
    event_type = "message.sent"
    step_name = "send_approved"

    def __init__(
        self,
        composer: ComposerClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._composer = composer
        self._publisher = publisher
        self._settings = settings

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        message_id = getattr(envelope.payload, "message_id", None)
        if message_id is None:
            return
        tenant_id = envelope.tenant_id

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            repo = FlowRepository(session)

            message = await self._composer.get_message(
                message_id, tenant_id=str(tenant_id), trace_id=envelope.trace_id
            )
            if message is None:
                return
            contact_id = message.get("contact_id")
            flows = await repo.list_flows(tenant_id=tenant_id, status="running", limit=200)
            flow = None
            for f in flows:
                drafted = f.progress.get("drafted_contact_ids") or []
                if contact_id and contact_id in [str(x) for x in drafted]:
                    flow = f
                    break
            if flow is None:
                return

            step = start_step(
                tenant_id=tenant_id,
                flow_id=flow.id,
                step_name=self.step_name,
                input_data={
                    "message_id": str(message_id),
                    "original_event_type": envelope.event_type,
                    "original_event_payload": envelope.payload.model_dump(mode="json"),
                },
                max_attempts=self._settings.max_step_retries,
            )
            await repo.add_step(step)
            complete_step(step, output_data={"message_id": str(message_id)})
            sent_ids = list(flow.progress.get("sent_message_ids") or [])
            sent_ids.append(str(message_id))
            flow.progress = {**flow.progress, "sent_message_ids": sent_ids}
            FLOW_STEPS_TOTAL.labels(step_name=self.step_name, status="completed").inc()
            await session.flush()
            await emit_flow_step_completed(self._publisher, flow, step, trace_id=envelope.trace_id)

            if flow.completed_steps >= flow.total_steps and flow.status == "running":
                flow.status = "completed"
                flow.finished_at = datetime.now(UTC)
                await session.flush()
                await emit_flow_completed(self._publisher, flow, trace_id=envelope.trace_id)
                logger.info("flow_completed", flow_id=str(flow.id))
