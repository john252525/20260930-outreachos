"""HTTP routes for reply-classifier."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from reply_classifier.api.deps import get_service
from reply_classifier.schemas import MarkHandledRequest, ReplyRead, ReplySummary
from reply_classifier.service import ReplyService

router = APIRouter(prefix="/replies", tags=["replies"])


@router.get("/{reply_id}", response_model=ReplyRead)
async def get_reply(
    reply_id: UUID,
    svc: ReplyService = Depends(get_service),
) -> ReplyRead:
    reply = await svc.get(reply_id)
    return ReplyRead.model_validate(reply)


@router.get("", response_model=list[ReplySummary])
async def list_replies(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    message_id: UUID | None = Query(None),
    contact_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ReplyService = Depends(get_service),
) -> list[ReplySummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    replies = await svc.list(
        tenant_id=tenant_id,
        status=status_filter,
        category=category,
        message_id=message_id,
        contact_id=contact_id,
        limit=limit,
        offset=offset,
    )
    return [ReplySummary.model_validate(r) for r in replies]


@router.post("/{reply_id}/handle", response_model=ReplyRead)
async def mark_handled(
    reply_id: UUID,
    data: MarkHandledRequest,
    request: Request,
    svc: ReplyService = Depends(get_service),
) -> ReplyRead:
    reply = await svc.mark_handled(
        reply_id=reply_id,
        handled_by=request.headers.get("X-User-Id", "anonymous"),
        outcome=data.outcome,
    )
    return ReplyRead.model_validate(reply)


@router.post("/{reply_id}/reclassify", response_model=ReplyRead)
async def reclassify(
    reply_id: UUID,
    svc: ReplyService = Depends(get_service),
) -> ReplyRead:
    reply = await svc.reclassify(reply_id=reply_id, trace_id=get_trace_id() or "")
    return ReplyRead.model_validate(reply)
