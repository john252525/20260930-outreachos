"""Business logic for tenants."""

from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError

from common.errors import ConflictError, NotFoundError
from db.rls import set_tenant_context
from db.types import generate_uuid7
from tenant_service.models import Tenant
from tenant_service.repository import TenantRepository
from tenant_service.schemas import TenantCreate, TenantUpdate

logger = structlog.get_logger()


class TenantService:
    def __init__(self, repo: TenantRepository) -> None:
        self._repo = repo

    @property
    def repo(self) -> TenantRepository:
        return self._repo

    async def create(self, data: TenantCreate, *, created_by: str = "system") -> Tenant:
        existing = await self._repo.get_by_slug(data.slug)
        if existing is not None:
            raise ConflictError(f"Tenant with slug '{data.slug}' already exists")
        tenant = Tenant(
            id=generate_uuid7(),
            name=data.name,
            slug=data.slug,
            status="active",
            is_sandbox=data.is_sandbox,
            created_by=created_by,
        )
        # RLS: INSERT ... RETURNING requires the new row to pass the SELECT
        # policy (USING id = app.tenant_id). A freshly created tenant is
        # allowed to see itself, so we scope the transaction to its own id.
        await set_tenant_context(self._repo.session, tenant.id)
        try:
            await self._repo.add(tenant)
        except IntegrityError as e:
            # Unique slug violation. RLS hides other tenants' rows from the
            # pre-check above, so the DB constraint is the source of truth.
            raise ConflictError(f"Tenant with slug '{data.slug}' already exists") from e
        # Create default settings for the new tenant.
        from db.types import generate_uuid7 as _uuid7
        from tenant_service.models import TenantSettings

        settings = TenantSettings(id=_uuid7(), tenant_id=tenant.id)
        self._repo.session.add(settings)
        await self._repo.session.flush()

        logger.info("tenant_created", tenant_id=str(tenant.id), slug=tenant.slug)
        return tenant

    async def get(self, tenant_id: UUID) -> Tenant:
        tenant = await self._repo.get(tenant_id)
        if tenant is None:
            raise NotFoundError(f"Tenant {tenant_id} not found")
        return tenant

    async def update(self, tenant_id: UUID, data: TenantUpdate) -> Tenant:
        tenant = await self.get(tenant_id)
        if data.name is not None:
            tenant.name = data.name
        if data.status is not None:
            tenant.status = data.status
        await self._repo.session.flush()
        return tenant

    async def archive(self, tenant_id: UUID) -> Tenant:
        tenant = await self.get(tenant_id)
        tenant.status = "archived"
        await self._repo.session.flush()
        return tenant

    async def restore(self, tenant_id: UUID) -> Tenant:
        tenant = await self.get(tenant_id)
        tenant.status = "active"
        await self._repo.session.flush()
        return tenant
