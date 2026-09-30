"""Contact-store FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from common.errors import AppError
from common.health import router as health_router
from common.logging import configure_logging
from common.middleware.errors import app_error_handler, unhandled_error_handler
from common.middleware.idempotency import IdempotencyMiddleware
from common.middleware.tenant import TenantMiddleware
from common.middleware.trace import TraceMiddleware
from common.redis import close_redis, init_redis
from contact_store.api.routes_companies import router as companies_router
from contact_store.api.routes_contacts import router as contacts_router
from contact_store.api.routes_stoplist import router as stoplist_router
from contact_store.config import Settings
from db.session import dispose_engine, init_engine
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher

logger = structlog.get_logger()


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

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Contact Store", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(companies_router)
    app.include_router(contacts_router)
    app.include_router(stoplist_router)

    return app


app = create_app()
