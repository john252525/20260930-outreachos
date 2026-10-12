"""Auto-revision FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from auto_revision.analysis.llm_advisor import LLMAdvisor
from auto_revision.analysis.metrics_analyzer import MetricsAnalyzer
from auto_revision.analysis.template_revisor import TemplateRevisor
from auto_revision.api.routes import router as revisions_router
from auto_revision.clients.analytics_client import AnalyticsClient
from auto_revision.clients.composer_client import ComposerClient
from auto_revision.clients.experiments_client import ExperimentsClient
from auto_revision.config import Settings
from auto_revision.llm.client import LLMClient
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

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    llm = LLMClient(settings)
    analytics = AnalyticsClient(settings.analytics_service_url)
    experiments = ExperimentsClient(settings.experiments_service_url)
    composer = ComposerClient(settings.composer_service_url)

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.llm = llm
    app.state.analytics = analytics
    app.state.experiments = experiments
    app.state.composer = composer
    app.state.analyzer = MetricsAnalyzer(analytics, settings)
    app.state.advisor = LLMAdvisor(llm)
    app.state.revisor = TemplateRevisor(llm)

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        await llm.close()
        await analytics.close()
        await experiments.close()
        await composer.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Auto Revision", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(revisions_router)

    return app


app = create_app()
