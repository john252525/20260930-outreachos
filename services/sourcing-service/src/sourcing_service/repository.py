"""Data access layer for sourcing-service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sourcing_service.models import SearchJob


class SearchJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, job_id: UUID) -> SearchJob | None:
        return await self._s.get(SearchJob, job_id)

    async def add(self, job: SearchJob) -> SearchJob:
        self._s.add(job)
        await self._s.flush()
        return job

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchJob]:
        stmt = select(SearchJob).where(SearchJob.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(SearchJob.status == status)
        stmt = stmt.order_by(SearchJob.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
