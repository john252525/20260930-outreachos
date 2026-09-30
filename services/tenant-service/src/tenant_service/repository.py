"""Data access layer for tenants."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenant_service.models import Tenant


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, tenant_id: UUID) -> Tenant | None:
        return await self._s.get(Tenant, tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list(
        self, *, status: str | None = None, include_archived: bool = False
    ) -> Sequence[Tenant]:
        stmt = select(Tenant)
        if status is not None:
            stmt = stmt.where(Tenant.status == status)
        elif not include_archived:
            stmt = stmt.where(Tenant.status != "archived")
        stmt = stmt.order_by(Tenant.created_at.desc())
        return (await self._s.execute(stmt)).scalars().all()

    async def add(self, tenant: Tenant) -> Tenant:
        self._s.add(tenant)
        await self._s.flush()
        return tenant
