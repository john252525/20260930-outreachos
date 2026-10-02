"""Review-queue FastAPI application."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

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
from contracts.base import EventEnvelope
from db.rls import set_tenant_context
from db.session import async_session_factory, dispose_engine, init_engine
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher
from nats_client.subscriber import Subscriber
from review_queue.api.routes import router as review_router
from review_queue.clients.composer_client import ComposerClient
from review_queue.config import Settings
from review_queue.repository import ReviewItemRepository
from review_queue.service import ReviewQueueService

logger = structlog.get_logger()


def _make_handler(app: FastAPI) -> Callable[[EventEnvelope[Any]], Awaitable[None]]:
    async def _on_message_drafted(envelope: EventEnvelope[Any]) -> None:
        tenant_id = envelope.tenant_id
        message_id = envelope.payload.message.id
        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            svc = ReviewQueueService(
                repo=ReviewItemRepository(session),
                composer=app.state.composer,
                publisher=app.state.publisher,
            )
            await svc.create_from_message(
                tenant_id=tenant_id,
                message_id=UUID(str(message_id)),
                trace_id=envelope.trace_id,
            )

    return _on_message_drafted


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
    app.state.composer = ComposerClient(settings.composer_service_url)

    subscriber = Subscriber(
        nats_conn.js,
        stream="BRIEFS",
        durable="review-queue-message-drafted",
        filter_subjects=["message.drafted.*"],
        handler=_make_handler(app),
    )
    await subscriber.start()
    task = asyncio.create_task(subscriber.run_forever())

    logger.info("service_started", service=settings.service_name)
    try:
        yield
    finally:
        task.cancel()
        await subscriber.stop()
        await app.state.composer.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Review Queue", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(review_router)

    return app


app = create_app()
