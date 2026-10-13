"""HTTP routes for campaign-service."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from campaign_service.api.deps import get_service
from campaign_service.schemas import (
    CampaignCreate,
    CampaignRead,
    CampaignSummary,
    CampaignUpdate,
)
from campaign_service.service import CampaignService
from common.context import get_tenant_id
from common.errors import ValidationError

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    svc: CampaignService = Depends(get_service),
) -> CampaignRead:
    campaign = await svc.create(tenant_id=_tenant(), data=data)
    return CampaignRead.model_validate(campaign)


@router.get("", response_model=list[CampaignSummary])
async def list_campaigns(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: CampaignService = Depends(get_service),
) -> list[CampaignSummary]:
    campaigns = await svc.list(
        tenant_id=_tenant(), status=status_filter, limit=limit, offset=offset
    )
    return [CampaignSummary.model_validate(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: UUID,
    svc: CampaignService = Depends(get_service),
) -> CampaignRead:
    return CampaignRead.model_validate(await svc.get(campaign_id))


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    svc: CampaignService = Depends(get_service),
) -> CampaignRead:
    return CampaignRead.model_validate(await svc.update(campaign_id=campaign_id, data=data))


@router.post("/{campaign_id}/archive", response_model=CampaignRead)
async def archive_campaign(
    campaign_id: UUID,
    svc: CampaignService = Depends(get_service),
) -> CampaignRead:
    return CampaignRead.model_validate(await svc.archive(campaign_id))


@router.get("/{campaign_id}/metrics")
async def campaign_metrics(
    campaign_id: UUID,
    svc: CampaignService = Depends(get_service),
) -> dict[str, Any]:
    return await svc.metrics(tenant_id=_tenant(), campaign_id=campaign_id)
