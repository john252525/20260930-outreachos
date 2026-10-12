"""Handle icp.generated → auto-start sourcing per segment."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from contracts.base import EventEnvelope
from db.rls import set_tenant_context
from db.session import async_session_factory
from nats_client.publisher import Publisher
from orchestrator.clients.icp_client import ICPClient
from orchestrator.clients.sourcing_client import SourcingClient
from orchestrator.clients.tenant_client import TenantClient
from orchestrator.config import Settings
from orchestrator.events import emit_flow_step_completed
from orchestrator.handlers.base import StepHandler, complete_step, start_step
from orchestrator.metrics import FLOW_STEPS_TOTAL
from orchestrator.repository import FlowRepository

logger = structlog.get_logger()


class ICPGeneratedHandler(StepHandler):
    event_type = "icp.generated"
    step_name = "start_sourcing"

    def __init__(
        self,
        icp_client: ICPClient,
        sourcing_client: SourcingClient,
        tenant_client: TenantClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._icp = icp_client
        self._sourcing = sourcing_client
        self._tenant = tenant_client
        self._publisher = publisher
        self._settings = settings

    async def handle(self, envelope: EventEnvelope[Any]) -> None:
        tenant_settings = await self._tenant.get_settings(str(envelope.tenant_id))
        auto = tenant_settings.get("auto_icp_to_sourcing", self._settings.auto_icp_to_sourcing)
        if not auto:
            return

        icp_payload = getattr(envelope.payload, "icp", None)
        if icp_payload is None:
            return
        icp_id = str(icp_payload.id)
        brief_id = str(icp_payload.brief_id)
        tenant_id = envelope.tenant_id

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            repo = FlowRepository(session)

            flow = await repo.find_by_brief(tenant_id, brief_id)
            if flow is None:
                logger.warning("flow_not_found_for_icp", icp_id=icp_id)
                return
            if flow.status != "running":
                logger.info(
                    "flow_not_running_skip_sourcing", flow_id=str(flow.id), status=flow.status
                )
                return

            flow.icp_id = UUID(icp_id)
            flow.current_step = self.step_name

            existing_step = await repo.get_step(flow.id, self.step_name)
            if existing_step is not None and existing_step.status in ("running", "completed"):
                return

            step = start_step(
                tenant_id=tenant_id,
                flow_id=flow.id,
                step_name=self.step_name,
                input_data={
                    "icp_id": icp_id,
                    "original_event_type": envelope.event_type,
                    "original_event_payload": envelope.payload.model_dump(mode="json"),
                },
                max_attempts=self._settings.max_step_retries,
            )
            await repo.add_step(step)
            await session.flush()

            icp = await self._icp.get_icp(
                icp_id, tenant_id=str(tenant_id), trace_id=envelope.trace_id
            )
            segments = (icp.get("payload") or {}).get("segments", [])
            if not segments:
                step.status = "failed"
                step.error = "No segments in ICP"
                step.finished_at = datetime.now(UTC)
                await session.flush()
                return

            search_job_ids: list[str] = []
            for segment in segments[: self._settings.max_sources_per_search]:
                try:
                    job = await self._sourcing.start_search(
                        tenant_id=str(tenant_id),
                        icp_id=icp_id,
                        segment_id=str(segment["id"]),
                        sources=flow.params.get("sources"),
                        limit_per_source=flow.params.get("limit_per_source"),
                        trace_id=envelope.trace_id,
                        idempotency_key=f"orchestrator:{flow.id}:search:{segment['id']}",
                    )
                    search_job_ids.append(str(job["id"]))
                except Exception as e:
                    logger.warning(
                        "sourcing_segment_failed", segment_id=segment.get("id"), error=str(e)
                    )

            if search_job_ids:
                flow.search_job_id = UUID(search_job_ids[0])
            complete_step(step, output_data={"search_job_ids": search_job_ids})
            flow.completed_steps = max(flow.completed_steps, 1) + 1
            FLOW_STEPS_TOTAL.labels(step_name=self.step_name, status="completed").inc()
            await session.flush()
            await emit_flow_step_completed(self._publisher, flow, step, trace_id=envelope.trace_id)
            logger.info("sourcing_started", flow_id=str(flow.id), jobs=len(search_job_ids))
