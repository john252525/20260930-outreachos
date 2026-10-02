"""HTTP routes for sourcing-service."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from sourcing_service.api.deps import get_service
from sourcing_service.schemas import (
    SearchCreateRequest,
    SearchJobRead,
    SearchJobSummary,
    SearchStats,
)
from sourcing_service.service import SearchOrchestrator

router = APIRouter(prefix="/searches", tags=["searches"])


@router.post("", response_model=SearchJobRead, status_code=status.HTTP_201_CREATED)
async def create_search(
    data: SearchCreateRequest,
    svc: SearchOrchestrator = Depends(get_service),
) -> SearchJobRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    job = await svc.create_and_run(
        tenant_id=tenant_id,
        icp_id=data.icp_id,
        segment_id=data.segment_id,
        sources=data.sources,
        limit_per_source=data.limit_per_source,
        urls=data.urls,
        trace_id=get_trace_id() or "",
    )
    return SearchJobRead.model_validate(job)


@router.get("/stats", response_model=SearchStats)
async def search_stats(
    period_days: int = Query(30, ge=1, le=365),
    svc: SearchOrchestrator = Depends(get_service),
) -> SearchStats:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    result = await svc.stats(tenant_id=tenant_id, period_days=period_days)
    return SearchStats(**result)


@router.get("", response_model=list[SearchJobSummary])
async def list_searches(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: SearchOrchestrator = Depends(get_service),
) -> list[SearchJobSummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    jobs = await svc.list(tenant_id=tenant_id, status=status_filter, limit=limit, offset=offset)
    return [SearchJobSummary.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=SearchJobRead)
async def get_search(
    job_id: UUID,
    svc: SearchOrchestrator = Depends(get_service),
) -> SearchJobRead:
    job = await svc.get(job_id)
    return SearchJobRead.model_validate(job)


@router.post("/{job_id}/retry-failed", response_model=SearchJobRead)
async def retry_failed(
    job_id: UUID,
    svc: SearchOrchestrator = Depends(get_service),
) -> SearchJobRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    job = await svc.retry_failed(job_id=job_id, tenant_id=tenant_id, trace_id=get_trace_id() or "")
    return SearchJobRead.model_validate(job)


@router.post("/{job_id}/cancel", response_model=SearchJobRead)
async def cancel_search(
    job_id: UUID,
    svc: SearchOrchestrator = Depends(get_service),
) -> SearchJobRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    job = await svc.cancel(job_id=job_id, tenant_id=tenant_id, trace_id=get_trace_id() or "")
    return SearchJobRead.model_validate(job)
