"""HTTP routes for analytics-service."""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from analytics_service.api.deps import get_service
from analytics_service.schemas import (
    CategoryMetric,
    Funnel,
    Overview,
    SegmentMetric,
    SenderMetric,
    SourcingStats,
    TemplateMetric,
)
from analytics_service.service import AnalyticsService
from common.context import get_tenant_id
from common.errors import ValidationError

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _default_from() -> date:
    return date.today() - timedelta(days=30)


def _tenant() -> Any:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.get("/overview", response_model=Overview)
async def overview(
    from_date: date = Query(default_factory=_default_from),
    to_date: date = Query(default_factory=date.today),
    svc: AnalyticsService = Depends(get_service),
) -> Overview:
    data = await svc.get_overview(tenant_id=_tenant(), from_date=from_date, to_date=to_date)
    return Overview.model_validate(data)


@router.get("/funnel", response_model=Funnel)
async def funnel(svc: AnalyticsService = Depends(get_service)) -> Funnel:
    data = await svc.get_funnel(tenant_id=_tenant())
    return Funnel.model_validate(data)


@router.get("/by-template", response_model=list[TemplateMetric])
async def by_template(
    from_date: date = Query(default_factory=_default_from),
    to_date: date = Query(default_factory=date.today),
    svc: AnalyticsService = Depends(get_service),
) -> list[TemplateMetric]:
    rows = await svc.get_by_template(tenant_id=_tenant(), from_date=from_date, to_date=to_date)
    return [TemplateMetric.model_validate(r) for r in rows]


@router.get("/by-sender", response_model=list[SenderMetric])
async def by_sender(
    from_date: date = Query(default_factory=_default_from),
    to_date: date = Query(default_factory=date.today),
    svc: AnalyticsService = Depends(get_service),
) -> list[SenderMetric]:
    rows = await svc.get_by_sender(tenant_id=_tenant(), from_date=from_date, to_date=to_date)
    return [SenderMetric.model_validate(r) for r in rows]


@router.get("/reply-categories", response_model=list[CategoryMetric])
async def reply_categories(
    from_date: date = Query(default_factory=_default_from),
    to_date: date = Query(default_factory=date.today),
    svc: AnalyticsService = Depends(get_service),
) -> list[CategoryMetric]:
    rows = await svc.get_reply_categories(tenant_id=_tenant(), from_date=from_date, to_date=to_date)
    return [CategoryMetric.model_validate(r) for r in rows]


@router.get("/sourcing", response_model=SourcingStats)
async def sourcing(
    from_date: date = Query(default_factory=_default_from),
    to_date: date = Query(default_factory=date.today),
    svc: AnalyticsService = Depends(get_service),
) -> SourcingStats:
    data = await svc.get_sourcing_stats(tenant_id=_tenant(), from_date=from_date, to_date=to_date)
    return SourcingStats.model_validate(data)


@router.get("/segments", response_model=list[SegmentMetric])
async def segments(
    from_date: date = Query(default_factory=_default_from),
    to_date: date = Query(default_factory=date.today),
    svc: AnalyticsService = Depends(get_service),
) -> list[SegmentMetric]:
    rows = await svc.get_segments(tenant_id=_tenant(), from_date=from_date, to_date=to_date)
    return [SegmentMetric.model_validate(r) for r in rows]


@router.get("/daily")
async def daily(
    from_date: date = Query(default_factory=_default_from),
    to_date: date = Query(default_factory=date.today),
    channel: str | None = Query(None),
    template_id: str | None = Query(None),
    svc: AnalyticsService = Depends(get_service),
) -> list[dict[str, Any]]:
    return await svc.get_daily(
        tenant_id=_tenant(),
        from_date=from_date,
        to_date=to_date,
        channel=channel,
        template_id=template_id,
    )


@router.get("/experiment-variants")
async def experiment_variants(
    experiment_id: UUID = Query(...),
    svc: AnalyticsService = Depends(get_service),
) -> list[dict[str, Any]]:
    return await svc.get_experiment_variants(tenant_id=_tenant(), experiment_id=experiment_id)
