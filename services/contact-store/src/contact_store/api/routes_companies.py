"""Company routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from contact_store.api.deps import get_company_service
from contact_store.schemas import (
    CompanyBulkResult,
    CompanyBulkUpsert,
    CompanyRead,
    CompanyUpsert,
    CompanyUpsertResult,
)
from contact_store.service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyUpsertResult, status_code=status.HTTP_201_CREATED)
async def upsert_company(
    data: CompanyUpsert,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyUpsertResult:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    company, action = await svc.upsert(
        tenant_id=tenant_id,
        payload=data.payload,
        status=data.status,
        trace_id=get_trace_id() or "",
    )
    return CompanyUpsertResult(
        company=CompanyRead.model_validate(company),
        action=action,
    )


@router.post("/bulk", response_model=CompanyBulkResult)
async def bulk_upsert(
    data: CompanyBulkUpsert,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyBulkResult:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    result = await svc.bulk_upsert(
        tenant_id=tenant_id,
        items=[item.model_dump() for item in data.items],
        trace_id=get_trace_id() or "",
    )
    return CompanyBulkResult(
        created=result["created"],
        updated=result["updated"],
        merged=result["merged"],
        results=[
            CompanyUpsertResult(
                company=CompanyRead.model_validate(r["company"]), action=r["action"]
            )
            for r in result["results"]
        ],
        errors=result["errors"],
    )


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: UUID,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = await svc.get(company_id)
    return CompanyRead.model_validate(company)


@router.get("", response_model=list[CompanyRead])
async def list_companies(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: CompanyService = Depends(get_company_service),
) -> list[CompanyRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    companies = await svc.list(
        tenant_id=tenant_id, status=status_filter, limit=limit, offset=offset
    )
    return [CompanyRead.model_validate(c) for c in companies]
