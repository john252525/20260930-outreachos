"""Composer service FastAPI application."""

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
from composer_service.api.routes import router as messages_router
from composer_service.api.routes_templates import router as templates_router
from composer_service.clients.brief_client import BriefClient
from composer_service.clients.contact_store_client import ContactStoreClient
from composer_service.clients.experiments_client import ExperimentsClient
from composer_service.clients.icp_client import ICPClient
from composer_service.config import Settings
from composer_service.llm.client import LLMClient
from composer_service.personalization.fact_checker import FactChecker
from composer_service.personalization.personalizer import Personalizer
from composer_service.templates.email_cold_outreach_v1 import EmailColdOutreachV1
from composer_service.templates.email_followup_v1 import EmailFollowupV1
from composer_service.templates.registry import TemplateRegistry
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

    registry = TemplateRegistry()
    registry.register(
        EmailColdOutreachV1(
            min_words=settings.min_body_words,
            max_words=settings.max_body_words,
            max_subject_len=settings.max_subject_length,
        )
    )
    registry.register(EmailFollowupV1())

    llm = LLMClient(settings)

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.contact_store = ContactStoreClient(settings.contact_store_url)
    app.state.experiments_client = ExperimentsClient(settings.experiments_service_url)
    app.state.brief_client = BriefClient(settings.brief_service_url)
    app.state.icp_client = ICPClient(settings.icp_service_url)
    app.state.llm = llm
    app.state.template_registry = registry
    app.state.personalizer = Personalizer(llm, settings)
    app.state.fact_checker = FactChecker(
        strict=settings.strict_fact_check,
        min_confidence=settings.min_fact_confidence,
    )

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        await app.state.contact_store.close()
        await app.state.experiments_client.close()
        await app.state.brief_client.close()
        await app.state.icp_client.close()
        await llm.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Composer Service", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(messages_router)
    app.include_router(templates_router)

    return app


app = create_app()
