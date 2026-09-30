"""HTTP routes for tenant-service."""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from common.context import get_trace_id
from nats_client.publisher import Publisher
from tenant_service.api.deps import get_publisher, get_service
from tenant_service.events import (
    emit_tenant_archived,
    emit_tenant_created,
    emit_tenant_restored,
    emit_tenant_updated,
)
from tenant_service.schemas import TenantCreate, TenantRead, TenantUpdate
from tenant_service.service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    svc: TenantService = Depends(get_service),
    publisher: Publisher = Depends(get_publisher),
) -> TenantRead:
    tenant = await svc.create(data)
    await emit_tenant_created(publisher, tenant, trace_id=get_trace_id() or "")
    return TenantRead.model_validate(tenant)


@router.get("", response_model=list[TenantRead])
async def list_tenants(
    status_filter: str | None = None,
    svc: TenantService = Depends(get_service),
) -> list[TenantRead]:
    tenants = await svc.repo.list(status=status_filter)
    return [TenantRead.model_validate(t) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: UUID,
    svc: TenantService = Depends(get_service),
) -> TenantRead:
    tenant = await svc.get(tenant_id)
    return TenantRead.model_validate(tenant)


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    svc: TenantService = Depends(get_service),
    publisher: Publisher = Depends(get_publisher),
) -> TenantRead:
    tenant = await svc.update(tenant_id, data)
    await emit_tenant_updated(publisher, tenant, trace_id=get_trace_id() or "")
    return TenantRead.model_validate(tenant)


@router.post("/{tenant_id}/archive", response_model=TenantRead)
async def archive_tenant(
    tenant_id: UUID,
    svc: TenantService = Depends(get_service),
    publisher: Publisher = Depends(get_publisher),
) -> TenantRead:
    tenant = await svc.archive(tenant_id)
    await emit_tenant_archived(publisher, tenant, trace_id=get_trace_id() or "")
    return TenantRead.model_validate(tenant)


@router.post("/{tenant_id}/restore", response_model=TenantRead)
async def restore_tenant(
    tenant_id: UUID,
    svc: TenantService = Depends(get_service),
    publisher: Publisher = Depends(get_publisher),
) -> TenantRead:
    tenant = await svc.restore(tenant_id)
    await emit_tenant_restored(publisher, tenant, trace_id=get_trace_id() or "")
    return TenantRead.model_validate(tenant)
