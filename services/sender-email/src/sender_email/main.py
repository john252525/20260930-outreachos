"""Sender-email FastAPI application."""

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
from common.redis import close_redis, get_redis, init_redis
from contracts.base import EventEnvelope
from db.rls import set_tenant_context
from db.session import async_session_factory, dispose_engine, init_engine
from nats_client.client import NATSConnection
from nats_client.publisher import Publisher
from nats_client.subscriber import Subscriber
from sender_email.api.routes import router as accounts_router
from sender_email.clients.composer_client import ComposerClient
from sender_email.clients.contact_store_client import ContactStoreClient
from sender_email.config import Settings
from sender_email.rampup.limiter import RampUpLimiter
from sender_email.repository import SenderRepository
from sender_email.service import RateLimitError, SenderService
from sender_email.smtp.account_manager import AccountManager, PasswordEncryptor

logger = structlog.get_logger()


class ApprovalNackError(Exception):
    """Signals a retryable failure — causes a delayed nack."""


def _make_handler(app: FastAPI) -> Callable[[EventEnvelope[Any]], Awaitable[None]]:
    async def _on_message_approved(envelope: EventEnvelope[Any]) -> None:
        tenant_id = envelope.tenant_id
        message_id = UUID(str(envelope.payload.message_id))
        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            svc = SenderService(
                repo=SenderRepository(session),
                composer=app.state.composer,
                contact_store=app.state.contact_store,
                encryptor=app.state.encryptor,
                limiter=RampUpLimiter(get_redis()),
                account_manager=app.state.account_manager,
                publisher=app.state.publisher,
                settings=app.state.settings,
            )
            try:
                await svc.send_approved_message(
                    tenant_id=tenant_id, message_id=message_id, trace_id=envelope.trace_id
                )
            except RateLimitError as e:
                # Retryable: surface as error so the subscriber nacks with delay.
                raise ApprovalNackError(str(e)) from e

    return _on_message_approved


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    encryptor = PasswordEncryptor(settings.sender_encryption_key)

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.composer = ComposerClient(settings.composer_service_url)
    app.state.contact_store = ContactStoreClient(settings.contact_store_url)
    app.state.encryptor = encryptor
    app.state.account_manager = AccountManager(encryptor)

    subscriber = Subscriber(
        nats_conn.js,
        stream="BRIEFS",
        durable="sender-email-message-approved",
        filter_subjects=["message.approved.*"],
        handler=_make_handler(app),
        batch_size=5,
        fetch_timeout=5.0,
    )
    await subscriber.start()
    task = asyncio.create_task(subscriber.run_forever())

    logger.info("service_started", service=settings.service_name, dry_run=settings.dry_run)
    try:
        yield
    finally:
        task.cancel()
        await subscriber.stop()
        await app.state.composer.close()
        await app.state.contact_store.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Sender Email", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(accounts_router)

    return app


app = create_app()
