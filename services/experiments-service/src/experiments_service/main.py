"""Experiments-service FastAPI application."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from sqlalchemy import text

from common.errors import AppError
from common.health import router as health_router
from common.logging import configure_logging
from common.middleware.errors import app_error_handler, unhandled_error_handler
from common.middleware.idempotency import IdempotencyMiddleware
from common.middleware.tenant import TenantMiddleware
from common.middleware.trace import TraceMiddleware
from common.redis import close_redis, init_redis
from db.rls import set_tenant_context
from db.session import async_session_factory, dispose_engine, init_engine
from experiments_service.api.routes import router as experiments_router
from experiments_service.clients.analytics_client import AnalyticsClient
from experiments_service.config import Settings
from experiments_service.repository import ExperimentRepository
from experiments_service.service import ExperimentService
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher

logger = structlog.get_logger()

TENANT_LIST_QUERY = text("SELECT id FROM tenants WHERE status <> 'deleted'")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.analytics = AnalyticsClient(settings.analytics_service_url)

    evaluate_task = asyncio.create_task(_evaluate_loop(app, settings))

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        evaluate_task.cancel()
        await app.state.analytics.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


async def _evaluate_loop(app: FastAPI, settings: Settings) -> None:
    if not settings.auto_evaluate_enabled:
        return
    while True:
        try:
            async with async_session_factory() as session:
                rows = (await session.execute(TENANT_LIST_QUERY)).all()
            for r in rows:
                tenant_id = r[0]
                async with async_session_factory() as session, session.begin():
                    await set_tenant_context(session, tenant_id)
                    svc = ExperimentService(
                        repo=ExperimentRepository(session),
                        analytics=app.state.analytics,
                        publisher=app.state.publisher,
                        settings=settings,
                    )
                    await svc.evaluate_running(tenant_id=tenant_id)
        except Exception as e:
            logger.exception("evaluate_loop_failed", error=str(e))
        await asyncio.sleep(settings.evaluate_interval_seconds)


def create_app() -> FastAPI:
    app = FastAPI(title="Experiments Service", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(experiments_router)

    return app


app = create_app()
