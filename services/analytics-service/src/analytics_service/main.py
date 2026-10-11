"""Analytics-service FastAPI application."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import FastAPI
from sqlalchemy import text

from analytics_service.alerts.engine import AlertEngine
from analytics_service.api.routes import router as analytics_router
from analytics_service.config import Settings
from analytics_service.db_admin import (
    admin_session_factory,
    dispose_admin_engine,
    init_admin_engine,
)
from analytics_service.refresher import MVRefresher
from analytics_service.repository import MetricsRepository
from common.errors import AppError
from common.health import router as health_router
from common.logging import configure_logging
from common.middleware.errors import app_error_handler, unhandled_error_handler
from common.middleware.idempotency import IdempotencyMiddleware
from common.middleware.tenant import TenantMiddleware
from common.middleware.trace import TraceMiddleware
from common.redis import close_redis, get_redis, init_redis
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher

logger = structlog.get_logger()

TENANT_LIST_QUERY = text("SELECT id FROM tenants WHERE status <> 'deleted'")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_admin_engine(settings.database_url_admin)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.redis = get_redis()
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")

    refresher = MVRefresher(admin_session_factory(), settings)
    refresh_task = asyncio.create_task(refresher.run_forever())
    alert_task = asyncio.create_task(_alert_loop(app, settings))

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        refresher.stop()
        refresh_task.cancel()
        alert_task.cancel()
        await nats_conn.close()
        await close_redis()
        await dispose_admin_engine()
        logger.info("service_stopped")


async def _alert_loop(app: FastAPI, settings: Settings) -> None:
    if not settings.alerts_enabled:
        return
    while True:
        try:
            async with admin_session_factory()() as session:
                rows = (await session.execute(TENANT_LIST_QUERY)).all()
                tenant_ids = [UUID(str(r[0])) for r in rows]
            async with admin_session_factory()() as session:
                engine = AlertEngine(MetricsRepository(session), app.state.publisher, settings)
                await engine.check_tenants(tenant_ids)
        except Exception as e:
            logger.exception("alert_loop_failed", error=str(e))
        await asyncio.sleep(settings.alert_check_interval_seconds)


def create_app() -> FastAPI:
    app = FastAPI(title="Analytics Service", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(analytics_router)

    return app


app = create_app()
