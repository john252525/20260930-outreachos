"""Data access layer for orchestrator."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models import Flow, FlowStep


class FlowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, flow_id: UUID) -> Flow | None:
        return await self._s.get(Flow, flow_id)

    async def find_by_brief(self, tenant_id: UUID, brief_id: str) -> Flow | None:
        stmt = (
            select(Flow)
            .where(Flow.tenant_id == tenant_id, Flow.brief_id == brief_id)
            .order_by(Flow.created_at.desc())
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def find_by_icp(self, tenant_id: UUID, icp_id: UUID) -> Flow | None:
        stmt = (
            select(Flow)
            .where(Flow.tenant_id == tenant_id, Flow.icp_id == icp_id)
            .order_by(Flow.created_at.desc())
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def find_by_search_job(self, tenant_id: UUID, search_job_id: UUID) -> Flow | None:
        stmt = (
            select(Flow)
            .where(Flow.tenant_id == tenant_id, Flow.search_job_id == search_job_id)
            .order_by(Flow.created_at.desc())
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def add_flow(self, flow: Flow) -> Flow:
        self._s.add(flow)
        await self._s.flush()
        return flow

    async def add_step(self, step: FlowStep) -> FlowStep:
        self._s.add(step)
        await self._s.flush()
        return step

    async def get_step(self, flow_id: UUID, step_name: str) -> FlowStep | None:
        stmt = select(FlowStep).where(FlowStep.flow_id == flow_id, FlowStep.step_name == step_name)
        return (await self._s.execute(stmt)).scalars().first()

    async def list_steps(self, flow_id: UUID) -> list[FlowStep]:
        stmt = (
            select(FlowStep).where(FlowStep.flow_id == flow_id).order_by(FlowStep.created_at.asc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def list_flows(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        flow_type: str | None = None,
        brief_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Flow]:
        stmt = select(Flow).where(Flow.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Flow.status == status)
        if flow_type:
            stmt = stmt.where(Flow.flow_type == flow_type)
        if brief_id:
            stmt = stmt.where(Flow.brief_id == brief_id)
        stmt = stmt.order_by(Flow.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def due_retries(
        self, tenant_id: UUID, *, now: datetime, limit: int = 10
    ) -> list[FlowStep]:
        stmt = (
            select(FlowStep)
            .where(
                FlowStep.tenant_id == tenant_id,
                FlowStep.status == "retry_scheduled",
                FlowStep.next_retry_at <= now,
            )
            .order_by(FlowStep.next_retry_at.asc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())
