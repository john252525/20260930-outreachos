"""Data access layer for experiments-service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from experiments_service.models import Experiment


class ExperimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, experiment_id: UUID) -> Experiment | None:
        return await self._s.get(Experiment, experiment_id)

    async def get_by_name(self, tenant_id: UUID, name: str) -> Experiment | None:
        stmt = select(Experiment).where(Experiment.tenant_id == tenant_id, Experiment.name == name)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add(self, experiment: Experiment) -> Experiment:
        self._s.add(experiment)
        await self._s.flush()
        return experiment

    async def list_all(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Experiment]:
        stmt = select(Experiment).where(Experiment.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Experiment.status == status)
        stmt = stmt.order_by(Experiment.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def list_running(self, tenant_id: UUID) -> list[Experiment]:
        stmt = select(Experiment).where(
            Experiment.tenant_id == tenant_id, Experiment.status == "running"
        )
        return list((await self._s.execute(stmt)).scalars().all())
