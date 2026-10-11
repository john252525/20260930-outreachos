"""FastAPI dependencies for analytics-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from analytics_service.db_admin import admin_session_factory
from analytics_service.repository import MetricsRepository
from analytics_service.service import AnalyticsService


async def get_service(request: Request) -> AsyncIterator[AnalyticsService]:
    session_factory = admin_session_factory()
    async with session_factory() as session:
        yield AnalyticsService(
            repo=MetricsRepository(session),
            cache=request.app.state.redis,
            settings=request.app.state.settings,
        )
