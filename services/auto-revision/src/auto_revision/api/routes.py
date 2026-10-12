"""HTTP routes for auto-revision."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from auto_revision.api.deps import get_service
from auto_revision.schemas import ProposeRequest, RejectRequest, RevisionRead, RevisionSummary
from auto_revision.service import RevisionService
from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError

router = APIRouter(prefix="/revisions", tags=["revisions"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.post("/propose", response_model=RevisionRead, status_code=status.HTTP_201_CREATED)
async def propose(
    data: ProposeRequest,
    svc: RevisionService = Depends(get_service),
) -> RevisionRead:
    revision = await svc.propose(
        tenant_id=_tenant(),
        trigger_type=data.trigger_type,
        trigger_context=data.trigger_context,
        trace_id=get_trace_id() or "",
    )
    return RevisionRead.model_validate(revision)


@router.get("", response_model=list[RevisionSummary])
async def list_revisions(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: RevisionService = Depends(get_service),
) -> list[RevisionSummary]:
    revisions = await svc.list(
        tenant_id=_tenant(), status=status_filter, limit=limit, offset=offset
    )
    return [RevisionSummary.model_validate(r) for r in revisions]


@router.get("/{revision_id}", response_model=RevisionRead)
async def get_revision(
    revision_id: UUID,
    svc: RevisionService = Depends(get_service),
) -> RevisionRead:
    return RevisionRead.model_validate(await svc.get(revision_id))


@router.post("/{revision_id}/approve", response_model=RevisionRead)
async def approve_revision(
    revision_id: UUID,
    request: Request,
    svc: RevisionService = Depends(get_service),
) -> RevisionRead:
    revision = await svc.approve(
        tenant_id=_tenant(),
        revision_id=revision_id,
        user_id=request.headers.get("X-User-Id", "anonymous"),
        trace_id=get_trace_id() or "",
    )
    return RevisionRead.model_validate(revision)


@router.post("/{revision_id}/reject", response_model=RevisionRead)
async def reject_revision(
    revision_id: UUID,
    data: RejectRequest,
    request: Request,
    svc: RevisionService = Depends(get_service),
) -> RevisionRead:
    revision = await svc.reject(
        revision_id=revision_id,
        user_id=request.headers.get("X-User-Id", "anonymous"),
        reason=data.reason,
        trace_id=get_trace_id() or "",
    )
    return RevisionRead.model_validate(revision)
