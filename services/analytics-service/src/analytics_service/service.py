"""Business logic for analytics-service."""

from datetime import date
from typing import Any, cast
from uuid import UUID

import structlog
from redis.asyncio import Redis

from analytics_service import serialization
from analytics_service.config import Settings
from analytics_service.repository import MetricsRepository

logger = structlog.get_logger()


class AnalyticsService:
    def __init__(
        self,
        *,
        repo: MetricsRepository,
        cache: "Redis[str]",
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._cache = cache
        self._settings = settings

    async def _cached(self, key: str, producer: Any) -> Any:
        cached = await self._cache.get(key)
        if cached:
            return serialization.loads(cached)
        value = await producer()
        await self._cache.setex(key, self._settings.cache_ttl_seconds, serialization.dumps(value))
        return value

    async def get_overview(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        key = f"analytics:overview:{tenant_id}:{from_date}:{to_date}"
        return cast(
            dict[str, Any],
            await self._cached(
                key,
                lambda: self._repo.overview(
                    tenant_id=tenant_id, from_date=from_date, to_date=to_date
                ),
            ),
        )

    async def get_funnel(self, *, tenant_id: UUID) -> dict[str, Any]:
        key = f"analytics:funnel:{tenant_id}"
        return cast(
            dict[str, Any],
            await self._cached(key, lambda: self._repo.replies.funnel(tenant_id=tenant_id)),
        )

    async def get_by_template(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        key = f"analytics:by-template:{tenant_id}:{from_date}:{to_date}"
        return cast(
            list[dict[str, Any]],
            await self._cached(
                key,
                lambda: self._repo.messages.by_template(
                    tenant_id=tenant_id, from_date=from_date, to_date=to_date
                ),
            ),
        )

    async def get_by_sender(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        key = f"analytics:by-sender:{tenant_id}:{from_date}:{to_date}"
        return cast(
            list[dict[str, Any]],
            await self._cached(
                key,
                lambda: self._repo.senders.by_sender(
                    tenant_id=tenant_id, from_date=from_date, to_date=to_date
                ),
            ),
        )

    async def get_reply_categories(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        key = f"analytics:reply-categories:{tenant_id}:{from_date}:{to_date}"
        return cast(
            list[dict[str, Any]],
            await self._cached(
                key,
                lambda: self._repo.replies.category_breakdown(
                    tenant_id=tenant_id, from_date=from_date, to_date=to_date
                ),
            ),
        )

    async def get_sourcing_stats(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        key = f"analytics:sourcing:{tenant_id}:{from_date}:{to_date}"
        return cast(
            dict[str, Any],
            await self._cached(
                key,
                lambda: self._repo.sourcing.summary(
                    tenant_id=tenant_id, from_date=from_date, to_date=to_date
                ),
            ),
        )

    async def get_segments(
        self, *, tenant_id: UUID, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        key = f"analytics:segments:{tenant_id}:{from_date}:{to_date}"
        return cast(
            list[dict[str, Any]],
            await self._cached(
                key,
                lambda: self._repo.segments.by_segment(
                    tenant_id=tenant_id, from_date=from_date, to_date=to_date
                ),
            ),
        )

    async def get_daily(
        self,
        *,
        tenant_id: UUID,
        from_date: date,
        to_date: date,
        channel: str | None = None,
        template_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._repo.messages.daily(
            tenant_id=tenant_id,
            from_date=from_date,
            to_date=to_date,
            channel=channel,
            template_id=template_id,
        )

    async def get_experiment_variants(
        self, *, tenant_id: UUID, experiment_id: UUID
    ) -> list[dict[str, Any]]:
        return await self._repo.experiments.variant_stats(
            tenant_id=tenant_id, experiment_id=experiment_id
        )
