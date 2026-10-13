"""Data access layer for campaign-service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campaign_service.models import Campaign


class CampaignRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @property
    def session(self) -> AsyncSession:
        return self._s

    async def get(self, campaign_id: UUID) -> Campaign | None:
        return await self._s.get(Campaign, campaign_id)

    async def get_by_name(self, tenant_id: UUID, name: str) -> Campaign | None:
        stmt = select(Campaign).where(Campaign.tenant_id == tenant_id, Campaign.name == name)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def add(self, campaign: Campaign) -> Campaign:
        self._s.add(campaign)
        await self._s.flush()
        return campaign

    async def list_all(
        self,
        *,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Campaign]:
        stmt = select(Campaign).where(Campaign.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Campaign.status == status)
        stmt = stmt.order_by(Campaign.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())
