"""Unit tests for campaign service (fake repo)."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from campaign_service.schemas import CampaignCreate
from campaign_service.service import CampaignService


class FakeRepo:
    def __init__(self) -> None:
        self._by_name: dict[str, Any] = {}

    @property
    def session(self) -> Any:
        class S:
            async def flush(self) -> None: ...
            async def refresh(self, *a: Any) -> None: ...
        return S()

    async def get_by_name(self, tenant_id: UUID, name: str) -> Any:
        return self._by_name.get(name)

    async def add(self, campaign: Any) -> Any:
        campaign.id = uuid4()
        self._by_name[campaign.name] = campaign
        return campaign


class FakeAnalytics:
    async def get_overview(self, **kw: Any) -> dict[str, Any]:
        return {"sent": 10, "replied": 2, "positive_count": 1, "reply_rate": 0.2}


def _service() -> CampaignService:
    from campaign_service.config import Settings

    s = Settings(
        SERVICE_NAME="campaign-service",
        DATABASE_URL="postgresql+asyncpg://x:y@localhost/db",
        NATS_URL="nats://localhost:4222",
        REDIS_URL="redis://localhost:6379/0",
    )
    return CampaignService(repo=FakeRepo(), analytics=FakeAnalytics(), settings=s)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_campaign() -> None:
    svc = _service()
    campaign = await svc.create(
        tenant_id=uuid4(), data=CampaignCreate(name="Q1")
    )
    assert campaign.name == "Q1"
    assert campaign.status == "draft"


@pytest.mark.asyncio
async def test_duplicate_name_conflict() -> None:
    from common.errors import ConflictError

    svc = _service()
    tid = uuid4()
    await svc.create(tenant_id=tid, data=CampaignCreate(name="Q1"))
    with pytest.raises(ConflictError):
        await svc.create(tenant_id=tid, data=CampaignCreate(name="Q1"))
