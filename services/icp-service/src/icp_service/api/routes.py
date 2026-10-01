"""HTTP routes for icp-service."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id, get_trace_id
from common.errors import NotFoundError, ValidationError
from icp_service.api.deps import get_service
from icp_service.schemas import ICPGenerateRequest, ICPRead, ICPSummary
from icp_service.service import ICPService

router = APIRouter(prefix="/icps", tags=["icps"])


@router.post("", response_model=ICPRead, status_code=status.HTTP_201_CREATED)
async def generate_icp(
    data: ICPGenerateRequest,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.generate(
        tenant_id=tenant_id, brief_id=data.brief_id, trace_id=get_trace_id() or ""
    )
    return ICPRead.model_validate(icp)


@router.get("", response_model=list[ICPSummary])
async def list_icps(
    brief_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ICPService = Depends(get_service),
) -> list[ICPSummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    if brief_id:
        icps = await svc.list_by_brief(tenant_id=tenant_id, brief_id=brief_id)
    else:
        icps = await svc.list(tenant_id=tenant_id, limit=limit, offset=offset)
    return [
        ICPSummary(
            id=i.id,
            brief_id=i.brief_id,
            version=i.version,
            is_active=i.is_active,
            segments_count=i.segments_count,
            llm_confidence=i.llm_confidence,
            created_at=i.created_at,
        )
        for i in icps
    ]


@router.get("/active/by-brief/{brief_id}", response_model=ICPRead)
async def get_active_icp(
    brief_id: str,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.get_active(tenant_id=tenant_id, brief_id=brief_id)
    if icp is None:
        raise NotFoundError(f"No active ICP for brief {brief_id}")
    return ICPRead.model_validate(icp)


@router.get("/{icp_id}", response_model=ICPRead)
async def get_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    icp = await svc.get(icp_id)
    return ICPRead.model_validate(icp)


@router.post("/{icp_id}/revise", response_model=ICPRead, status_code=status.HTTP_201_CREATED)
async def revise_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.revise(tenant_id=tenant_id, icp_id=icp_id, trace_id=get_trace_id() or "")
    return ICPRead.model_validate(icp)


@router.post("/{icp_id}/activate", response_model=ICPRead)
async def activate_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.activate(tenant_id=tenant_id, icp_id=icp_id, trace_id=get_trace_id() or "")
    return ICPRead.model_validate(icp)


@router.post("/{icp_id}/deactivate", response_model=ICPRead)
async def deactivate_icp(
    icp_id: UUID,
    svc: ICPService = Depends(get_service),
) -> ICPRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    icp = await svc.deactivate(tenant_id=tenant_id, icp_id=icp_id, trace_id=get_trace_id() or "")
    return ICPRead.model_validate(icp)
