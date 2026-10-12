"""Handle reply.received → mark flow progress by reply."""

from typing import Any

import structlog

from contracts.base import EventEnvelope
from db.rls import set_tenant_context
from db.session import async_session_factory
from orchestrator.clients.composer_client import ComposerClient
from orchestrator.config import Settings
from orchestrator.handlers.base import StepHandler
from orchestrator.repository import FlowRepository

logger = structlog.get_logger()


class ReplyReceivedHandler(StepHandler):
    event_type = "reply.received"
    step_name = "reply_received"

    def __init__(
        self,
        composer: ComposerClient,
        settings: Settings,
    ) -> None:
        self._composer = composer
        self._settings = settings

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        reply = getattr(envelope.payload, "reply", None)
        if reply is None:
            return
        message_id = getattr(reply, "message_id", None)
        tenant_id = envelope.tenant_id
        if message_id is None:
            return

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            repo = FlowRepository(session)

            message = await self._composer.get_message(
                message_id, tenant_id=str(tenant_id), trace_id=envelope.trace_id
            )
            if message is None:
                return
            contact_id = message.get("contact_id")

            flows = await repo.list_flows(tenant_id=tenant_id, limit=200)
            for f in flows:
                sent_ids = [str(x) for x in (f.progress.get("sent_message_ids") or [])]
                drafted = [str(x) for x in (f.progress.get("drafted_contact_ids") or [])]
                if str(message_id) in sent_ids or (contact_id and str(contact_id) in drafted):
                    replied = list(f.progress.get("replied_message_ids") or [])
                    replied.append(str(message_id))
                    f.progress = {**f.progress, "replied_message_ids": replied}
                    await session.flush()
                    logger.info(
                        "flow_reply_tracked",
                        flow_id=str(f.id),
                        message_id=str(message_id),
                    )
                    break
