"""LLM gateway FastAPI application."""

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
from llm_gateway.api.routes import router as llm_router
from llm_gateway.config import Settings
from llm_gateway.langfuse_client import LangfuseClient
from llm_gateway.providers.registry import ProviderRegistry

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    init_redis(settings.redis_url)

    registry = ProviderRegistry(settings)
    langfuse = (
        LangfuseClient(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
        )
        if settings.langfuse_enabled
        else None
    )

    app.state.settings = settings
    app.state.registry = registry
    app.state.langfuse = langfuse

    logger.info(
        "service_started",
        service=settings.service_name,
        langfuse_enabled=bool(langfuse and langfuse.enabled),
    )
    try:
        yield
    finally:
        if langfuse is not None:
            langfuse.flush()
        await registry.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Gateway", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(llm_router)

    return app


app = create_app()
