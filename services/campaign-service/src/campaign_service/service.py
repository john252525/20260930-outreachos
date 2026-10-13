"""Business logic for campaign-service."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from campaign_service.clients.analytics_client import AnalyticsClient
from campaign_service.config import Settings
from campaign_service.models import Campaign
from campaign_service.repository import CampaignRepository
from campaign_service.schemas import CampaignCreate, CampaignUpdate
from common.errors import ConflictError, NotFoundError

logger = structlog.get_logger()


class CampaignService:
    def __init__(
        self,
        *,
        repo: CampaignRepository,
        analytics: AnalyticsClient,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._analytics = analytics
        self._settings = settings

    async def create(self, *, tenant_id: UUID, data: CampaignCreate) -> Campaign:
        existing = await self._repo.get_by_name(tenant_id, data.name)
        if existing is not None:
            raise ConflictError(f"Campaign '{data.name}' already exists")
        campaign = Campaign(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            owner_user_id=data.owner_user_id,
            status="draft",
            start_date=data.start_date,
            end_date=data.end_date,
            goals=data.goals,
            budget=data.budget,
            tags=data.tags,
        )
        await self._repo.add(campaign)
        await self._repo.session.refresh(campaign)
        logger.info("campaign_created", campaign_id=str(campaign.id))
        return campaign

    async def update(self, *, campaign_id: UUID, data: CampaignUpdate) -> Campaign:
        campaign = await self.get(campaign_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(campaign, field, value)
        await self._flush(campaign)
        return campaign

    async def get(self, campaign_id: UUID) -> Campaign:
        campaign = await self._repo.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"Campaign {campaign_id} not found")
        return campaign

    async def list(
        self, *, tenant_id: UUID, status: str | None, limit: int, offset: int
    ) -> list[Campaign]:
        return await self._repo.list_all(
            tenant_id=tenant_id, status=status, limit=limit, offset=offset
        )

    async def archive(self, campaign_id: UUID) -> Campaign:
        campaign = await self.get(campaign_id)
        campaign.status = "archived"
        campaign.archived_at = datetime.now(UTC)
        await self._flush(campaign)
        return campaign

    async def metrics(self, *, tenant_id: UUID, campaign_id: UUID) -> dict[str, Any]:
        campaign = await self.get(campaign_id)
        if campaign.status == "archived" and campaign.metrics:
            return campaign.metrics

        to_date = date.today()
        from_date = to_date - timedelta(days=90)
        data = await self._analytics.get_overview(
            tenant_id=str(tenant_id),
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )
        metrics = {
            "sent": data.get("sent", 0),
            "replied": data.get("replied", 0),
            "positive_replied": data.get("positive_count", 0),
            "bounced": data.get("bounced", 0),
            "reply_rate": data.get("reply_rate", 0.0),
            "positive_reply_rate": data.get("positive_reply_rate", 0.0),
            "meetings_booked": campaign.goals.get("meetings_booked", 0),
            "refreshed_at": datetime.now(UTC).isoformat(),
        }
        campaign.metrics = metrics
        await self._flush(campaign)
        return metrics

    async def _flush(self, campaign: Campaign) -> None:
        await self._repo.session.flush()
        await self._repo.session.refresh(campaign)
