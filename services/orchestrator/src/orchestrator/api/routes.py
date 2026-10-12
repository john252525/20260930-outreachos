"""HTTP routes for orchestrator."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from orchestrator.api.deps import get_service
from orchestrator.schemas import FlowRead, FlowStepRead, FlowSummary, TriggerDraftRequest
from orchestrator.service import OrchestratorService

router = APIRouter(tags=["flows"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.get("/flows", response_model=list[FlowSummary])
async def list_flows(
    status_filter: str | None = Query(None, alias="status"),
    flow_type: str | None = Query(None),
    brief_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: OrchestratorService = Depends(get_service),
) -> list[FlowSummary]:
    flows = await svc.list_flows(
        tenant_id=_tenant(),
        status=status_filter,
        flow_type=flow_type,
        brief_id=brief_id,
        limit=limit,
        offset=offset,
    )
    return [FlowSummary.model_validate(f) for f in flows]


@router.get("/flows/{flow_id}", response_model=FlowRead)
async def get_flow(
    flow_id: UUID,
    svc: OrchestratorService = Depends(get_service),
) -> FlowRead:
    return FlowRead.model_validate(await svc.get_flow(flow_id))


@router.get("/flows/{flow_id}/steps", response_model=list[FlowStepRead])
async def get_flow_steps(
    flow_id: UUID,
    svc: OrchestratorService = Depends(get_service),
) -> list[FlowStepRead]:
    steps = await svc.get_flow_steps(flow_id)
    return [FlowStepRead.model_validate(s) for s in steps]


@router.post("/flows/{flow_id}/pause", response_model=FlowRead)
async def pause_flow(
    flow_id: UUID,
    svc: OrchestratorService = Depends(get_service),
) -> FlowRead:
    return FlowRead.model_validate(await svc.pause_flow(flow_id))


@router.post("/flows/{flow_id}/resume", response_model=FlowRead)
async def resume_flow(
    flow_id: UUID,
    svc: OrchestratorService = Depends(get_service),
) -> FlowRead:
    return FlowRead.model_validate(await svc.resume_flow(flow_id))


@router.post("/flows/{flow_id}/cancel", response_model=FlowRead)
async def cancel_flow(
    flow_id: UUID,
    svc: OrchestratorService = Depends(get_service),
) -> FlowRead:
    return FlowRead.model_validate(await svc.cancel_flow(flow_id))


@router.post("/flows/{flow_id}/trigger-draft", response_model=FlowRead)
async def trigger_draft(
    flow_id: UUID,
    data: TriggerDraftRequest,
    svc: OrchestratorService = Depends(get_service),
) -> FlowRead:
    flow = await svc.trigger_draft(
        tenant_id=_tenant(),
        flow_id=flow_id,
        data=data,
        trace_id=get_trace_id() or "",
    )
    return FlowRead.model_validate(flow)


@router.get("/stats")
async def stats(svc: OrchestratorService = Depends(get_service)) -> dict[str, Any]:
    return await svc.stats(tenant_id=_tenant())
