"""Data access layer for briefs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brief_service.models import Brief


class BriefRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, brief_id: UUID) -> Brief | None:
        return await self._s.get(Brief, brief_id)

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Brief]:
        stmt = select(Brief).where(Brief.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(Brief.status == status)
        stmt = stmt.order_by(Brief.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def add(self, brief: Brief) -> Brief:
        self._s.add(brief)
        await self._s.flush()
        return brief
