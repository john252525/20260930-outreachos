"""Template override routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from common.context import get_tenant_id
from common.errors import NotFoundError, ValidationError
from composer_service.api.deps import get_service
from composer_service.schemas import TemplateOverrideCreate, TemplateOverrideRead
from composer_service.service import ComposerService

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/overrides", response_model=list[TemplateOverrideRead])
async def list_overrides(
    svc: ComposerService = Depends(get_service),
) -> list[TemplateOverrideRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    overrides = await svc.list_overrides(tenant_id=tenant_id)
    return [TemplateOverrideRead.model_validate(o) for o in overrides]


@router.post("/overrides", response_model=TemplateOverrideRead, status_code=status.HTTP_201_CREATED)
async def create_override(
    data: TemplateOverrideCreate,
    svc: ComposerService = Depends(get_service),
) -> TemplateOverrideRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    override = await svc.create_override(tenant_id=tenant_id, data=data)
    return TemplateOverrideRead.model_validate(override)


@router.post("/overrides/{override_id}/activate", response_model=TemplateOverrideRead)
async def activate_override(
    override_id: UUID,
    svc: ComposerService = Depends(get_service),
) -> TemplateOverrideRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    override = await svc.set_override_active(
        tenant_id=tenant_id, override_id=override_id, is_active=True
    )
    if override is None:
        raise NotFoundError(f"Override {override_id} not found")
    return TemplateOverrideRead.model_validate(override)


@router.post("/overrides/{override_id}/deactivate", response_model=TemplateOverrideRead)
async def deactivate_override(
    override_id: UUID,
    svc: ComposerService = Depends(get_service),
) -> TemplateOverrideRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    override = await svc.set_override_active(
        tenant_id=tenant_id, override_id=override_id, is_active=False
    )
    if override is None:
        raise NotFoundError(f"Override {override_id} not found")
    return TemplateOverrideRead.model_validate(override)
