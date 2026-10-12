"""Orchestrator FastAPI application."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Response
from nats.js.api import DeliverPolicy
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from common.errors import AppError
from common.health import router as health_router
from common.logging import configure_logging
from common.middleware.errors import app_error_handler, unhandled_error_handler
from common.middleware.idempotency import IdempotencyMiddleware
from common.middleware.tenant import TenantMiddleware
from common.middleware.trace import TraceMiddleware
from common.redis import close_redis, get_redis, init_redis
from contracts.base import EventEnvelope
from db.session import dispose_engine, init_engine
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher
from nats_client.subscriber import Subscriber
from orchestrator.api.routes import router as flows_router
from orchestrator.clients.composer_client import ComposerClient
from orchestrator.clients.contact_store_client import ContactStoreClient
from orchestrator.clients.icp_client import ICPClient
from orchestrator.clients.review_queue_client import ReviewQueueClient, RevisionClient
from orchestrator.clients.sourcing_client import SourcingClient
from orchestrator.clients.tenant_client import TenantClient
from orchestrator.config import Settings
from orchestrator.db_admin import dispose_admin_engine, init_admin_engine
from orchestrator.handlers.analytics_alert import AnalyticsAlertHandler
from orchestrator.handlers.brief_completed import BriefCompletedHandler
from orchestrator.handlers.contacts_found import ContactsFoundHandler
from orchestrator.handlers.icp_generated import ICPGeneratedHandler
from orchestrator.handlers.message_approved import MessageApprovedHandler
from orchestrator.handlers.message_drafted import MessageDraftedHandler
from orchestrator.handlers.message_sent import MessageSentHandler
from orchestrator.handlers.reply_received import ReplyReceivedHandler
from orchestrator.retry_worker import RetryWorker
from orchestrator.router import EventRouter

logger = structlog.get_logger()

BRIEFS_SUBJECTS = [
    "brief.completed.*",
    "icp.generated.*",
    "message.drafted.*",
    "message.approved.*",
    "message.sent.*",
    "reply.received.*",
    "analytics.alert.*",
]
CONTACTS_SUBJECTS = ["contacts.found.*"]


def _make_handler(router: EventRouter) -> Callable[[EventEnvelope[Any]], Awaitable[None]]:
    async def _on_event(envelope: EventEnvelope[Any]) -> None:
        await router.route(envelope)

    return _on_event


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
    publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.publisher = publisher

    icp_client = ICPClient(settings.icp_service_url)
    sourcing_client = SourcingClient(settings.sourcing_service_url)
    composer = ComposerClient(settings.composer_service_url)
    contact_store = ContactStoreClient(settings.contact_store_url)
    review_queue = ReviewQueueClient(settings.review_queue_url)
    revision_client = RevisionClient(settings.revision_service_url)
    tenant_client = TenantClient(settings.tenant_service_url, get_redis())

    app.state.icp_client = icp_client
    app.state.sourcing_client = sourcing_client
    app.state.composer = composer
    app.state.contact_store = contact_store
    app.state.review_queue = review_queue
    app.state.revision_client = revision_client
    app.state.tenant_client = tenant_client

    router = EventRouter()
    router.register(BriefCompletedHandler(icp_client, tenant_client, publisher, settings))
    router.register(
        ICPGeneratedHandler(icp_client, sourcing_client, tenant_client, publisher, settings)
    )
    router.register(ContactsFoundHandler(composer, contact_store, icp_client, publisher, settings))
    router.register(MessageDraftedHandler())
    router.register(MessageApprovedHandler())
    router.register(MessageSentHandler(composer, publisher, settings))
    router.register(ReplyReceivedHandler(composer, settings))
    router.register(AnalyticsAlertHandler(revision_client, settings))
    app.state.router = router

    subscriber_briefs = Subscriber(
        nats_conn.js,
        stream="BRIEFS",
        durable=settings.nats_durable_name,
        filter_subjects=BRIEFS_SUBJECTS,
        handler=_make_handler(router),
        batch_size=10,
        fetch_timeout=5.0,
        deliver_policy=DeliverPolicy.NEW,
    )
    subscriber_contacts = Subscriber(
        nats_conn.js,
        stream="CONTACTS",
        durable=f"{settings.nats_durable_name}-contacts",
        filter_subjects=CONTACTS_SUBJECTS,
        handler=_make_handler(router),
        batch_size=10,
        fetch_timeout=5.0,
        deliver_policy=DeliverPolicy.NEW,
    )
    await subscriber_briefs.start()
    await subscriber_contacts.start()
    briefs_task = asyncio.create_task(subscriber_briefs.run_forever())
    contacts_task = asyncio.create_task(subscriber_contacts.run_forever())

    retry_worker = RetryWorker(router, settings)
    retry_task = asyncio.create_task(retry_worker.run_forever())

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        retry_worker.stop()
        retry_task.cancel()
        briefs_task.cancel()
        contacts_task.cancel()
        await subscriber_briefs.stop()
        await subscriber_contacts.stop()
        await icp_client.close()
        await sourcing_client.close()
        await composer.close()
        await contact_store.close()
        await review_queue.close()
        await revision_client.close()
        await tenant_client.close()
        await nats_conn.close()
        await close_redis()
        await dispose_admin_engine()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Orchestrator", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(
        TenantMiddleware,
        skip_paths={"/healthz", "/readyz", "/metrics", "/docs", "/openapi.json", "/redoc", "/"},
    )
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(flows_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
