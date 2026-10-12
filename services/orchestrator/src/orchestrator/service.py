"""Business logic for orchestrator (API side)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select

from common.errors import NotFoundError, ValidationError
from orchestrator.clients.composer_client import ComposerClient
from orchestrator.clients.contact_store_client import ContactStoreClient
from orchestrator.clients.icp_client import ICPClient
from orchestrator.config import Settings
from orchestrator.models import Flow, FlowStep
from orchestrator.repository import FlowRepository
from orchestrator.schemas import TriggerDraftRequest

logger = structlog.get_logger()


class OrchestratorService:
    def __init__(
        self,
        *,
        repo: FlowRepository,
        composer: ComposerClient,
        contact_store: ContactStoreClient,
        icp_client: ICPClient,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._composer = composer
        self._contact_store = contact_store
        self._icp = icp_client
        self._settings = settings

    async def list_flows(self, *, tenant_id: UUID, **kwargs: Any) -> list[Flow]:
        return await self._repo.list_flows(tenant_id=tenant_id, **kwargs)

    async def get_flow(self, flow_id: UUID) -> Flow:
        flow = await self._repo.get(flow_id)
        if flow is None:
            raise NotFoundError(f"Flow {flow_id} not found")
        return flow

    async def get_flow_steps(self, flow_id: UUID) -> list[FlowStep]:
        await self.get_flow(flow_id)
        return await self._repo.list_steps(flow_id)

    async def pause_flow(self, flow_id: UUID) -> Flow:
        flow = await self.get_flow(flow_id)
        if flow.status != "running":
            raise ValidationError(f"Cannot pause flow with status {flow.status}")
        flow.status = "paused"
        await self._flush(flow)
        return flow

    async def resume_flow(self, flow_id: UUID) -> Flow:
        flow = await self.get_flow(flow_id)
        if flow.status != "paused":
            raise ValidationError(f"Cannot resume flow with status {flow.status}")
        flow.status = "running"
        await self._flush(flow)
        return flow

    async def cancel_flow(self, flow_id: UUID) -> Flow:
        flow = await self.get_flow(flow_id)
        if flow.status in ("completed", "cancelled"):
            raise ValidationError(f"Cannot cancel flow with status {flow.status}")
        flow.status = "cancelled"
        flow.finished_at = datetime.now(UTC)
        await self._flush(flow)
        return flow

    async def trigger_draft(
        self,
        *,
        tenant_id: UUID,
        flow_id: UUID,
        data: TriggerDraftRequest,
        trace_id: str = "",
    ) -> Flow:
        flow = await self.get_flow(flow_id)
        if flow.status not in ("paused", "running"):
            raise ValidationError(f"Cannot trigger draft for flow with status {flow.status}")

        contact_ids: list[UUID] = []
        if data.contact_ids:
            contact_ids = data.contact_ids
        else:
            known = [UUID(str(x)) for x in (flow.progress.get("drafted_contact_ids") or [])]
            if known:
                contact_ids = known
            else:
                contacts = await self._contact_store.list_contacts(
                    tenant_id=str(tenant_id), status="candidate", limit=data.max_contacts or 100
                )
                contact_ids = [UUID(str(c["id"])) for c in contacts]

        if not contact_ids:
            raise ValidationError("No contacts available to draft")

        if flow.icp_id is None:
            raise ValidationError("Flow has no ICP; cannot draft")

        segment_id = flow.params.get("segment_id")
        if not segment_id:
            icp = await self._icp.get_icp(
                str(flow.icp_id), tenant_id=str(tenant_id), trace_id=trace_id
            )
            segments = (icp.get("payload") or {}).get("segments", [])
            if segments:
                segment_id = str(segments[0]["id"])
                flow.params = {**flow.params, "segment_id": segment_id}

        created = 0
        for cid in contact_ids:
            try:
                payload: dict[str, Any] = {
                    "contact_id": str(cid),
                    "icp_id": str(flow.icp_id),
                    "segment_id": str(segment_id or ""),
                    "channel": data.channel,
                }
                if data.template_id:
                    payload["template_id"] = data.template_id
                for key in ("sender_from_name", "sender_from_email", "sender_signature"):
                    if data.sender_config.get(key):
                        payload[key] = data.sender_config[key]
                await self._composer.draft(
                    tenant_id=str(tenant_id),
                    payload=payload,
                    trace_id=trace_id,
                    idempotency_key=f"orchestrator:{flow.id}:draft:{cid}",
                )
                created += 1
            except Exception as e:
                logger.warning("trigger_draft_contact_failed", contact_id=str(cid), error=str(e))

        drafted = [str(x) for x in (flow.progress.get("drafted_contact_ids") or [])]
        flow.progress = {
            **flow.progress,
            "drafted_contact_ids": sorted(set(drafted) | {str(c) for c in contact_ids}),
        }
        flow.status = "running"
        flow.current_step = "draft_messages"
        await self._flush(flow)
        logger.info("trigger_draft_done", flow_id=str(flow.id), created=created)
        return flow

    async def stats(self, *, tenant_id: UUID) -> dict[str, Any]:
        flow_rows = (
            await self._repo.session.execute(
                select(Flow.status, Flow.flow_type, func.count())
                .where(Flow.tenant_id == tenant_id)
                .group_by(Flow.status, Flow.flow_type)
            )
        ).all()
        step_rows = (
            await self._repo.session.execute(
                select(
                    FlowStep.step_name,
                    FlowStep.status,
                    func.count(),
                    func.avg(FlowStep.duration_ms),
                    func.sum(FlowStep.attempts),
                )
                .where(FlowStep.tenant_id == tenant_id)
                .group_by(FlowStep.step_name, FlowStep.status)
            )
        ).all()
        return {
            "flows": [{"status": r[0], "flow_type": r[1], "count": int(r[2])} for r in flow_rows],
            "steps": [
                {
                    "step_name": r[0],
                    "status": r[1],
                    "count": int(r[2]),
                    "avg_duration_ms": float(r[3]) if r[3] is not None else None,
                    "total_attempts": int(r[4] or 0),
                }
                for r in step_rows
            ],
        }

    async def _flush(self, flow: Flow) -> None:
        await self._repo.session.flush()
        await self._repo.session.refresh(flow)
