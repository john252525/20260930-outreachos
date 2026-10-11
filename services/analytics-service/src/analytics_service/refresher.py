"""Background worker refreshing materialized views."""

import asyncio

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from analytics_service.config import Settings

logger = structlog.get_logger()

MV_LIST = [
    "analytics.mv_daily_message_metrics",
    "analytics.mv_daily_reply_metrics",
    "analytics.mv_daily_sender_metrics",
    "analytics.mv_daily_sourcing_metrics",
    "analytics.mv_funnel",
]


class MVRefresher:
    """Periodically REFRESH all materialized views (admin/owner session)."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], settings: Settings
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._stopped = False

    async def run_forever(self) -> None:
        if not self._settings.mv_refresh_enabled:
            logger.info("mv_refresh_disabled")
            return
        while not self._stopped:
            try:
                await self.refresh_all()
            except Exception as e:
                logger.exception("mv_refresh_failed", error=str(e))
            await asyncio.sleep(self._settings.mv_refresh_interval_seconds)

    async def refresh_all(self) -> None:
        async with self._session_factory() as session:
            for mv in MV_LIST:
                try:
                    await session.execute(text(f"REFRESH MATERIALIZED VIEW {mv}"))
                    await session.commit()
                    logger.info("mv_refreshed", mv=mv)
                except Exception as e:
                    logger.warning("mv_refresh_error", mv=mv, error=str(e))
                    await session.rollback()

    def stop(self) -> None:
        self._stopped = True
