"""HTTP routes for review-queue."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from review_queue.api.deps import get_service
from review_queue.schemas import (
    ApproveRequest,
    AssignRequest,
    BulkApproveRequest,
    EditRequest,
    RejectRequest,
    ReviewItemRead,
)
from review_queue.service import ReviewQueueService

router = APIRouter(prefix="/review-items", tags=["review"])


@router.get("", response_model=list[ReviewItemRead])
async def list_items(
    status_filter: str | None = Query("pending", alias="status"),
    priority: str | None = Query(None),
    assigned_to: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ReviewQueueService = Depends(get_service),
) -> list[ReviewItemRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    items = await svc.list(
        tenant_id=tenant_id,
        status=status_filter,
        priority=priority,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return [ReviewItemRead.model_validate(i) for i in items]


@router.post("/bulk-approve")
async def bulk_approve(
    data: BulkApproveRequest,
    request: Request,
    svc: ReviewQueueService = Depends(get_service),
) -> dict[str, Any]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return await svc.bulk_approve(
        tenant_id=tenant_id,
        item_ids=data.item_ids,
        user_id=request.headers.get("X-User-Id", "anonymous"),
        trace_id=get_trace_id() or "",
    )


@router.get("/{item_id}", response_model=ReviewItemRead)
async def get_item(
    item_id: UUID,
    svc: ReviewQueueService = Depends(get_service),
) -> ReviewItemRead:
    item = await svc.get(item_id)
    return ReviewItemRead.model_validate(item)


@router.post("/{item_id}/approve", response_model=ReviewItemRead)
async def approve(
    item_id: UUID,
    data: ApproveRequest,
    request: Request,
    svc: ReviewQueueService = Depends(get_service),
) -> ReviewItemRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    item = await svc.approve(
        tenant_id=tenant_id,
        item_id=item_id,
        user_id=request.headers.get("X-User-Id", "anonymous"),
        scheduled_send_at=data.scheduled_send_at,
        trace_id=get_trace_id() or "",
    )
    return ReviewItemRead.model_validate(item)


@router.post("/{item_id}/reject", response_model=ReviewItemRead)
async def reject(
    item_id: UUID,
    data: RejectRequest,
    request: Request,
    svc: ReviewQueueService = Depends(get_service),
) -> ReviewItemRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    item = await svc.reject(
        tenant_id=tenant_id,
        item_id=item_id,
        user_id=request.headers.get("X-User-Id", "anonymous"),
        reason=data.reason,
        note=data.note,
        trace_id=get_trace_id() or "",
    )
    return ReviewItemRead.model_validate(item)


@router.post("/{item_id}/edit", response_model=ReviewItemRead)
async def edit(
    item_id: UUID,
    data: EditRequest,
    request: Request,
    svc: ReviewQueueService = Depends(get_service),
) -> ReviewItemRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    item = await svc.edit(
        tenant_id=tenant_id,
        item_id=item_id,
        subject=data.subject,
        body_text=data.body_text,
        user_id=request.headers.get("X-User-Id", "anonymous"),
        trace_id=get_trace_id() or "",
    )
    return ReviewItemRead.model_validate(item)


@router.post("/{item_id}/assign", response_model=ReviewItemRead)
async def assign(
    item_id: UUID,
    data: AssignRequest,
    svc: ReviewQueueService = Depends(get_service),
) -> ReviewItemRead:
    item = await svc.assign(item_id=item_id, assigned_to=data.assigned_to)
    return ReviewItemRead.model_validate(item)
