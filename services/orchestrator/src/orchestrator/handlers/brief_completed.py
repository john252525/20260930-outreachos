"""Handle brief.completed → auto-generate ICP."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from contracts.base import EventEnvelope
from db.rls import set_tenant_context
from db.session import async_session_factory
from nats_client.publisher import Publisher
from orchestrator.clients.icp_client import ICPClient
from orchestrator.clients.tenant_client import TenantClient
from orchestrator.config import Settings
from orchestrator.errors import is_retryable
from orchestrator.events import emit_flow_failed, emit_flow_started, emit_flow_step_completed
from orchestrator.handlers.base import (
    StepHandler,
    complete_step,
    schedule_retry,
    start_step,
)
from orchestrator.metrics import FLOW_STEPS_TOTAL, FLOWS_TOTAL
from orchestrator.models import Flow
from orchestrator.repository import FlowRepository

logger = structlog.get_logger()

TOTAL_STEPS = 4


class BriefCompletedHandler(StepHandler):
    event_type = "brief.completed"
    step_name = "generate_icp"

    def __init__(
        self,
        icp_client: ICPClient,
        tenant_client: TenantClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._icp = icp_client
        self._tenant = tenant_client
        self._publisher = publisher
        self._settings = settings

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        tenant_settings = await self._tenant.get_settings(str(envelope.tenant_id))
        auto = tenant_settings.get("auto_brief_to_icp", self._settings.auto_brief_to_icp)
        if not auto:
            logger.info("brief_to_icp_skipped_manual_mode")
            return

        brief = getattr(envelope.payload, "brief", None)
        if brief is None:
            return
        brief_id = str(brief.id)
        tenant_id = envelope.tenant_id

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            repo = FlowRepository(session)

            existing = await repo.find_by_brief(tenant_id, brief_id)
            if existing is not None and existing.icp_id is not None:
                logger.info("flow_exists_for_brief", flow_id=str(existing.id), brief_id=brief_id)
                # Reconcile a stuck step (e.g. after a retry that found the flow already done).
                stuck = await repo.get_step(existing.id, self.step_name)
                if stuck is not None and stuck.status in ("running", "retry_scheduled"):
                    complete_step(stuck, output_data={"icp_id": str(existing.icp_id)})
                    FLOW_STEPS_TOTAL.labels(step_name=self.step_name, status="completed").inc()
                    await session.flush()
                return

            if existing is not None:
                # Flow exists but ICP is not generated yet — continue the work.
                flow = existing
                flow.status = "running"
                flow.current_step = self.step_name
                step = await repo.get_step(flow.id, self.step_name)
                if step is None:
                    step = start_step(
                        tenant_id=tenant_id,
                        flow_id=flow.id,
                        step_name=self.step_name,
                        input_data={
                            "brief_id": brief_id,
                            "original_event_type": envelope.event_type,
                            "original_event_payload": envelope.payload.model_dump(mode="json"),
                        },
                        max_attempts=self._settings.max_step_retries,
                    )
                    await repo.add_step(step)
                else:
                    step.status = "running"
                    step.started_at = datetime.now(UTC)
                    await session.flush()
            else:
                flow = Flow(
                    tenant_id=tenant_id,
                    flow_type="brief_to_outreach",
                    status="running",
                    brief_id=brief_id,
                    params={
                        "sources": tenant_settings.get("default_sources")
                        or self._settings.default_sources,
                        "limit_per_source": tenant_settings.get("default_limit_per_source")
                        or self._settings.default_limit_per_source,
                        "channel": tenant_settings.get("default_channel")
                        or self._settings.default_channel,
                        "auto_draft": tenant_settings.get(
                            "auto_contacts_to_drafts", self._settings.auto_contacts_to_drafts
                        ),
                        "max_contacts_per_flow": tenant_settings.get(
                            "default_max_contacts_per_flow"
                        )
                        or self._settings.default_max_contacts_per_flow,
                    },
                    current_step=self.step_name,
                    total_steps=TOTAL_STEPS,
                    started_at=datetime.now(UTC),
                )
                await repo.add_flow(flow)
                FLOWS_TOTAL.labels(status="running", flow_type="brief_to_outreach").inc()

                step = start_step(
                    tenant_id=tenant_id,
                    flow_id=flow.id,
                    step_name=self.step_name,
                    input_data={
                        "brief_id": brief_id,
                        "original_event_type": envelope.event_type,
                        "original_event_payload": envelope.payload.model_dump(mode="json"),
                    },
                    max_attempts=self._settings.max_step_retries,
                )
                await repo.add_step(step)
            await emit_flow_started(self._publisher, flow, trace_id=envelope.trace_id)

            try:
                icp = await self._icp.generate_icp(
                    tenant_id=str(tenant_id),
                    brief_id=brief_id,
                    trace_id=envelope.trace_id,
                )
                icp_id = icp["id"]
                flow.icp_id = UUID(icp_id)
                flow.completed_steps = 1
                complete_step(
                    step,
                    output_data={
                        "icp_id": icp_id,
                        "segments_count": icp.get("segments_count", 0),
                    },
                )
                FLOW_STEPS_TOTAL.labels(step_name=self.step_name, status="completed").inc()
                await session.flush()
                await emit_flow_step_completed(
                    self._publisher, flow, step, trace_id=envelope.trace_id
                )
                logger.info("flow_step_completed", step=self.step_name, icp_id=icp_id)
            except Exception as e:
                logger.exception("brief_completed_handler_failed", brief_id=brief_id)
                step.attempts += 1
                step.finished_at = datetime.now(UTC)
                terminal = (not is_retryable(e)) or step.attempts >= step.max_attempts
                if terminal:
                    step.status = "failed"
                    step.error = str(e)
                    flow.status = "failed"
                    flow.failed_steps = 1
                    flow.error = f"Step {self.step_name} failed after {step.attempts} attempts"
                    flow.finished_at = datetime.now(UTC)
                    FLOW_STEPS_TOTAL.labels(step_name=self.step_name, status="failed").inc()
                    await session.flush()
                    await emit_flow_failed(self._publisher, flow, step, trace_id=envelope.trace_id)
                else:
                    schedule_retry(
                        step, error=str(e), delay_seconds=self._settings.retry_delay_seconds
                    )
                    await session.flush()
