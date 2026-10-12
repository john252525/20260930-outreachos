"""HTTP routes for composer-service."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from composer_service.api.deps import get_service
from composer_service.schemas import (
    DraftRequest,
    MessageRead,
    MessageSummary,
    MessageUpdate,
)
from composer_service.service import ComposerService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def draft_message(
    data: DraftRequest,
    svc: ComposerService = Depends(get_service),
) -> MessageRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    msg = await svc.draft(tenant_id=tenant_id, data=data, trace_id=get_trace_id() or "")
    return MessageRead.model_validate(msg)


@router.get("", response_model=list[MessageSummary])
async def list_messages(
    status_filter: str | None = Query(None, alias="status"),
    contact_id: UUID | None = Query(None),
    channel: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ComposerService = Depends(get_service),
) -> list[MessageSummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    messages = await svc.list_messages(
        tenant_id=tenant_id,
        status=status_filter,
        contact_id=contact_id,
        channel=channel,
        limit=limit,
        offset=offset,
    )
    return [MessageSummary.model_validate(m) for m in messages]


@router.get("/{message_id}", response_model=MessageRead)
async def get_message(
    message_id: UUID,
    svc: ComposerService = Depends(get_service),
) -> MessageRead:
    msg = await svc.get(message_id)
    return MessageRead.model_validate(msg)


@router.patch("/{message_id}", response_model=MessageRead)
async def update_message(
    message_id: UUID,
    data: MessageUpdate,
    svc: ComposerService = Depends(get_service),
) -> MessageRead:
    msg = await svc.update(message_id, data)
    return MessageRead.model_validate(msg)
