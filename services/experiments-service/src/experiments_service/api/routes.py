"""HTTP routes for experiments-service."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from experiments_service.api.deps import get_service
from experiments_service.schemas import (
    AssignRequest,
    AssignResponse,
    ExperimentCreate,
    ExperimentRead,
    ExperimentSummary,
)
from experiments_service.service import ExperimentService

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.post("", response_model=ExperimentRead, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    data: ExperimentCreate,
    svc: ExperimentService = Depends(get_service),
) -> ExperimentRead:
    exp = await svc.create(tenant_id=_tenant(), data=data, trace_id=get_trace_id() or "")
    return ExperimentRead.model_validate(exp)


@router.get("", response_model=list[ExperimentSummary])
async def list_experiments(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ExperimentService = Depends(get_service),
) -> list[ExperimentSummary]:
    exps = await svc.list(tenant_id=_tenant(), status=status_filter, limit=limit, offset=offset)
    return [ExperimentSummary.model_validate(e) for e in exps]


@router.get("/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(
    experiment_id: UUID,
    svc: ExperimentService = Depends(get_service),
) -> ExperimentRead:
    return ExperimentRead.model_validate(await svc.get(experiment_id))


@router.post("/{experiment_id}/start", response_model=ExperimentRead)
async def start_experiment(
    experiment_id: UUID,
    svc: ExperimentService = Depends(get_service),
) -> ExperimentRead:
    return ExperimentRead.model_validate(
        await svc.start(tenant_id=_tenant(), experiment_id=experiment_id)
    )


@router.post("/{experiment_id}/pause", response_model=ExperimentRead)
async def pause_experiment(
    experiment_id: UUID,
    svc: ExperimentService = Depends(get_service),
) -> ExperimentRead:
    return ExperimentRead.model_validate(
        await svc.pause(tenant_id=_tenant(), experiment_id=experiment_id)
    )


@router.post("/{experiment_id}/evaluate", response_model=ExperimentRead)
async def evaluate_experiment(
    experiment_id: UUID,
    svc: ExperimentService = Depends(get_service),
) -> ExperimentRead:
    exp = await svc.evaluate(
        tenant_id=_tenant(), experiment_id=experiment_id, trace_id=get_trace_id() or ""
    )
    return ExperimentRead.model_validate(exp)


@router.post("/{experiment_id}/assign", response_model=AssignResponse)
async def assign_variant(
    experiment_id: UUID,
    data: AssignRequest,
    svc: ExperimentService = Depends(get_service),
) -> AssignResponse:
    return await svc.assign(
        tenant_id=_tenant(), experiment_id=experiment_id, contact_id=data.contact_id
    )
