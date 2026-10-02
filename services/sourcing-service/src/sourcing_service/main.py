"""Sourcing service FastAPI application."""

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
from sourcing_service.api.routes import router as searches_router
from sourcing_service.clients.contact_store_client import ContactStoreClient
from sourcing_service.clients.icp_client import ICPClient
from sourcing_service.config import Settings
from sourcing_service.connectors.enricher import EnricherConnector, HunterProvider
from sourcing_service.connectors.registry import ConnectorRegistry
from sourcing_service.connectors.registry_connector import DaDataProvider, RegistryConnector
from sourcing_service.connectors.serper import SerperConnector
from sourcing_service.connectors.website_parser import WebsiteParserConnector
from sourcing_service.connectors.yandex_xml import YandexXMLConnector
from sourcing_service.llm.client import LLMClient
from sourcing_service.normalization.normalizer import Normalizer
from sourcing_service.scoring.scorer import Scorer

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    registry = ConnectorRegistry()
    registry.register(
        SerperConnector(
            api_key=settings.serper_api_key,
            base_url=settings.serper_base_url,
            rate_limit_per_sec=settings.serper_rate_limit_per_sec,
        )
    )
    registry.register(
        YandexXMLConnector(user=settings.yandex_xml_user, key=settings.yandex_xml_key)
    )
    registry.register(WebsiteParserConnector())
    if settings.dadata_api_key and settings.dadata_secret_key:
        registry.register(
            RegistryConnector(DaDataProvider(settings.dadata_api_key, settings.dadata_secret_key))
        )
    if settings.hunter_api_key:
        registry.register(EnricherConnector(HunterProvider(settings.hunter_api_key)))

    llm = LLMClient(settings)

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.connector_registry = registry
    app.state.icp_client = ICPClient(settings.icp_service_url)
    app.state.contact_store = ContactStoreClient(settings.contact_store_url)
    app.state.llm = llm
    app.state.normalizer = Normalizer(llm)
    app.state.scorer = Scorer(min_threshold=settings.min_score_threshold)
    app.state.running_tasks = {}

    logger.info(
        "service_started",
        service=settings.service_name,
        connectors=registry.list_available(),
    )
    try:
        yield
    finally:
        for task in list(app.state.running_tasks.values()):
            task.cancel()
        await registry.close_all()
        await app.state.icp_client.close()
        await app.state.contact_store.close()
        await llm.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Sourcing Service", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(searches_router)

    return app


app = create_app()
