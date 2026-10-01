"""Data access layer for icp-service."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from icp_service.models import ICP


class ICPRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, icp_id: UUID) -> ICP | None:
        return await self._s.get(ICP, icp_id)

    async def list_by_brief(self, tenant_id: UUID, brief_id: str) -> list[ICP]:
        stmt = (
            select(ICP)
            .where(ICP.tenant_id == tenant_id, ICP.brief_id == brief_id)
            .order_by(ICP.version.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def get_active(self, tenant_id: UUID, brief_id: str) -> ICP | None:
        stmt = select(ICP).where(
            ICP.tenant_id == tenant_id,
            ICP.brief_id == brief_id,
            ICP.is_active.is_(True),
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get_max_version(self, tenant_id: UUID, brief_id: str) -> int:
        stmt = (
            select(ICP.version)
            .where(ICP.tenant_id == tenant_id, ICP.brief_id == brief_id)
            .order_by(ICP.version.desc())
            .limit(1)
        )
        result = (await self._s.execute(stmt)).scalar_one_or_none()
        return result or 0

    async def deactivate_all(self, tenant_id: UUID, brief_id: str) -> None:
        stmt = (
            update(ICP)
            .where(ICP.tenant_id == tenant_id, ICP.brief_id == brief_id, ICP.is_active.is_(True))
            .values(is_active=False)
        )
        await self._s.execute(stmt)

    async def add(self, icp: ICP) -> ICP:
        self._s.add(icp)
        await self._s.flush()
        return icp

    async def list(self, *, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[ICP]:
        stmt = (
            select(ICP)
            .where(ICP.tenant_id == tenant_id)
            .order_by(ICP.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self._s.execute(stmt)).scalars().all())
