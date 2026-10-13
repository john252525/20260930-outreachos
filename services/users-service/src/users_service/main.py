"""Users-service FastAPI application."""

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
from db.session import dispose_engine, init_engine
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher
from users_service.api.routes_audit import router as audit_router
from users_service.api.routes_auth import router as auth_router
from users_service.api.routes_invitations import router as invitations_router
from users_service.api.routes_users import router as users_router
from users_service.clients_tenant import TenantClient
from users_service.config import Settings
from users_service.db_admin import dispose_admin_engine, init_admin_engine

logger = structlog.get_logger()

SKIP_PATHS = {
    "/healthz",
    "/readyz",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
    "/auth/me",
    "/auth/switch-tenant",
    "/auth/logout",
}
# These endpoints are called before a tenant is selected.
SKIP_RULES = [("POST", "/auth/register"), ("POST", "/auth/login")]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    if settings.database_url_admin:
        init_admin_engine(settings.database_url_admin)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.tenant_client = TenantClient(settings.tenant_service_url)

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        await app.state.tenant_client.close()
        await nats_conn.close()
        await close_redis()
        await dispose_admin_engine()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Users Service", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware, skip_paths=SKIP_PATHS, skip_rules=SKIP_RULES)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(invitations_router)
    app.include_router(audit_router)

    return app


app = create_app()
