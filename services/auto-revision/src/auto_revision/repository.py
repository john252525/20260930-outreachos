"""Data access layer for auto-revision."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auto_revision.models import Revision


class RevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, revision_id: UUID) -> Revision | None:
        return await self._s.get(Revision, revision_id)

    async def add(self, revision: Revision) -> Revision:
        self._s.add(revision)
        await self._s.flush()
        return revision

    async def list_all(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Revision]:
        stmt = select(Revision).where(Revision.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Revision.status == status)
        stmt = stmt.order_by(Revision.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def find_pending_for_template(self, tenant_id: UUID, template_id: str) -> Revision | None:
        stmt = (
            select(Revision)
            .where(
                Revision.tenant_id == tenant_id,
                Revision.template_id == template_id,
                Revision.status == "pending",
            )
            .order_by(Revision.created_at.desc())
        )
        return (await self._s.execute(stmt)).scalars().first()
