"""Handle contacts.found → optionally draft messages or pause for manual step."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from contracts.base import EventEnvelope
from db.rls import set_tenant_context
from db.session import async_session_factory
from nats_client.publisher import Publisher
from orchestrator.clients.composer_client import ComposerClient
from orchestrator.clients.contact_store_client import ContactStoreClient
from orchestrator.clients.icp_client import ICPClient
from orchestrator.config import Settings
from orchestrator.events import emit_flow_step_completed
from orchestrator.handlers.base import StepHandler, complete_step, start_step
from orchestrator.metrics import FLOW_STEPS_TOTAL
from orchestrator.repository import FlowRepository

logger = structlog.get_logger()


class ContactsFoundHandler(StepHandler):
    event_type = "contacts.found"
    step_name = "draft_messages"

    def __init__(
        self,
        composer: ComposerClient,
        contact_store: ContactStoreClient,
        icp_client: ICPClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._composer = composer
        self._contact_store = contact_store
        self._icp = icp_client
        self._publisher = publisher
        self._settings = settings

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        search_job_id = getattr(envelope.payload, "search_job_id", None)
        tenant_id = envelope.tenant_id
        if search_job_id is None:
            return

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            repo = FlowRepository(session)

            flow = await repo.find_by_search_job(tenant_id, UUID(str(search_job_id)))
            if flow is None:
                logger.info("flow_not_found_for_search_job", search_job_id=str(search_job_id))
                return
            if flow.status != "running":
                return

            existing_step = await repo.get_step(flow.id, self.step_name)
            if existing_step is not None and existing_step.status in ("running", "completed"):
                return

            if not flow.params.get("auto_draft"):
                flow.status = "paused"
                flow.current_step = self.step_name
                await session.flush()
                logger.info("contacts_found_awaiting_manual_draft", flow_id=str(flow.id))
                return

            contact_ids = [str(c) for c in getattr(envelope.payload, "contact_ids", [])]
            max_contacts = int(
                flow.params.get("max_contacts_per_flow")
                or self._settings.default_max_contacts_per_flow
            )
            await self._draft_for_contacts(
                repo=repo,
                flow=flow,
                tenant_id=tenant_id,
                contact_ids=contact_ids[:max_contacts],
                envelope=envelope,
            )

    async def _draft_for_contacts(
        self,
        *,
        repo: FlowRepository,
        flow: Any,
        tenant_id: UUID,
        contact_ids: list[str],
        envelope: EventEnvelope[Any],
    ) -> None:
        step = start_step(
            tenant_id=tenant_id,
            flow_id=flow.id,
            step_name=self.step_name,
            input_data={
                "contact_ids": contact_ids,
                "original_event_type": envelope.event_type,
                "original_event_payload": envelope.payload.model_dump(mode="json"),
            },
            max_attempts=self._settings.max_step_retries,
        )
        await repo.add_step(step)
        await repo.session.flush()

        if flow.icp_id is None:
            step.status = "failed"
            step.error = "flow has no icp_id"
            step.finished_at = datetime.now(UTC)
            await repo.session.flush()
            return

        segment_id = flow.params.get("segment_id")
        if not segment_id:
            try:
                icp = await self._icp.get_icp(
                    str(flow.icp_id), tenant_id=str(tenant_id), trace_id=envelope.trace_id
                )
                segments = (icp.get("payload") or {}).get("segments", [])
                if segments:
                    segment_id = str(segments[0]["id"])
                    flow.params = {**flow.params, "segment_id": segment_id}
            except Exception as e:
                logger.warning("icp_fetch_failed", flow_id=str(flow.id), error=str(e))

        created = 0
        for cid in contact_ids:
            try:
                payload = {
                    "contact_id": cid,
                    "icp_id": str(flow.icp_id),
                    "segment_id": str(segment_id or ""),
                    "channel": flow.params.get("channel", "email"),
                    "template_id": flow.params.get("template_id"),
                    "sender_from_name": (flow.params.get("sender_config") or {}).get(
                        "sender_from_name"
                    ),
                    "sender_from_email": (flow.params.get("sender_config") or {}).get(
                        "sender_from_email"
                    ),
                    "sender_signature": (flow.params.get("sender_config") or {}).get(
                        "sender_signature"
                    ),
                }
                payload = {k: v for k, v in payload.items() if v is not None}
                await self._composer.draft(
                    tenant_id=str(tenant_id),
                    payload=payload,
                    trace_id=envelope.trace_id,
                    idempotency_key=f"orchestrator:{flow.id}:draft:{cid}",
                )
                created += 1
            except Exception as e:
                logger.warning("draft_contact_failed", contact_id=cid, error=str(e))

        complete_step(step, output_data={"created": created, "requested": len(contact_ids)})
        flow.completed_steps += 1
        flow.current_step = "draft_messages_completed"
        drafted = [str(x) for x in (flow.progress.get("drafted_contact_ids") or [])]
        flow.progress = {
            **flow.progress,
            "drafted_contact_ids": sorted(set(drafted) | set(contact_ids)),
        }
        FLOW_STEPS_TOTAL.labels(step_name=self.step_name, status="completed").inc()
        await repo.session.flush()
        await emit_flow_step_completed(self._publisher, flow, step, trace_id=envelope.trace_id)
        logger.info("drafts_created", flow_id=str(flow.id), created=created)
