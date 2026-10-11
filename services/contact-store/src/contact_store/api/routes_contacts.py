"""Contact routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from contact_store.api.deps import get_contact_service
from contact_store.schemas import (
    ContactBulkResult,
    ContactBulkUpsert,
    ContactRead,
    ContactStatusUpdate,
    ContactUpsert,
    ContactUpsertResult,
    OutreachHistoryUpdate,
)
from contact_store.service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactUpsertResult, status_code=status.HTTP_201_CREATED)
async def upsert_contact(
    data: ContactUpsert,
    svc: ContactService = Depends(get_contact_service),
) -> ContactUpsertResult | JSONResponse:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    contact, action = await svc.upsert(
        tenant_id=tenant_id,
        payload=data.payload,
        status=data.status,
        trace_id=get_trace_id() or "",
    )
    if contact is None:
        reason = action.split(":", 1)[1] if ":" in action else "blocked"
        return JSONResponse({"status": "blocked", "reason": reason}, status_code=409)
    return ContactUpsertResult(contact=ContactRead.model_validate(contact), action=action)


@router.post("/bulk", response_model=ContactBulkResult)
async def bulk_upsert(
    data: ContactBulkUpsert,
    svc: ContactService = Depends(get_contact_service),
) -> ContactBulkResult:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    result = await svc.bulk_upsert(
        tenant_id=tenant_id,
        items=[item.model_dump() for item in data.items],
        trace_id=get_trace_id() or "",
    )
    return ContactBulkResult(
        created=result["created"],
        updated=result["updated"],
        merged=result["merged"],
        blocked=result["blocked"],
        results=[
            ContactUpsertResult(
                contact=ContactRead.model_validate(r["contact"]), action=r["action"]
            )
            for r in result["results"]
        ],
        errors=result["errors"],
    )


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(
    contact_id: UUID,
    svc: ContactService = Depends(get_contact_service),
) -> ContactRead:
    contact = await svc.get(contact_id)
    return ContactRead.model_validate(contact)


@router.get("", response_model=list[ContactRead])
async def list_contacts(
    status_filter: str | None = Query(None, alias="status"),
    company_id: UUID | None = Query(None),
    role_category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: ContactService = Depends(get_contact_service),
) -> list[ContactRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    contacts = await svc.list(
        tenant_id=tenant_id,
        status=status_filter,
        company_id=company_id,
        role_category=role_category,
        limit=limit,
        offset=offset,
    )
    return [ContactRead.model_validate(c) for c in contacts]


@router.post("/{contact_id}/status", response_model=ContactRead)
async def update_status(
    contact_id: UUID,
    data: ContactStatusUpdate,
    svc: ContactService = Depends(get_contact_service),
) -> ContactRead:
    contact = await svc.update_status(contact_id, status=data.status, trace_id=get_trace_id() or "")
    return ContactRead.model_validate(contact)


@router.patch("/{contact_id}/outreach-history", response_model=ContactRead)
async def update_outreach_history(
    contact_id: UUID,
    data: OutreachHistoryUpdate,
    svc: ContactService = Depends(get_contact_service),
) -> ContactRead:
    contact = await svc.update_outreach_history(
        contact_id,
        replied_positive=data.replied_positive,
        last_reply_at=data.last_reply_at,
        last_contacted_at=data.last_contacted_at,
    )
    return ContactRead.model_validate(contact)
