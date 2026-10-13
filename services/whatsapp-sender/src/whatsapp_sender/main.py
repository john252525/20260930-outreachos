"""WhatsApp-sender FastAPI application."""

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
from whatsapp_sender.api.routes import router as whatsapp_router
from whatsapp_sender.clients.composer_client import ComposerClient
from whatsapp_sender.clients.contact_store_client import ContactStoreClient
from whatsapp_sender.clients.tenant_client import TenantClient
from whatsapp_sender.config import Settings
from whatsapp_sender.encryptor import SecretEncryptor
from whatsapp_sender.repository import WhatsAppRepository
from whatsapp_sender.service import WhatsAppSenderService
from whatsapp_sender.session_window import SessionWindowChecker

logger = structlog.get_logger()


def _make_handler(app: FastAPI) -> Callable[[EventEnvelope[Any]], Awaitable[None]]:
    async def _on_message_approved(envelope: EventEnvelope[Any]) -> None:
        tenant_id = envelope.tenant_id
        message_id = UUID(str(envelope.payload.message_id))
        message = await app.state.composer.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=envelope.trace_id
        )
        if message is None or message.get("channel") != "whatsapp":
            return
        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            svc = WhatsAppSenderService(
                repo=WhatsAppRepository(session),
                composer=app.state.composer,
                contact_store=app.state.contact_store,
                tenant_client=app.state.tenant_client,
                encryptor=app.state.encryptor,
                window=app.state.window,
                publisher=app.state.publisher,
                settings=app.state.settings,
            )
            try:
                await svc.send_approved_message(
                    tenant_id=tenant_id, message_id=message_id, trace_id=envelope.trace_id
                )
            except Exception as e:
                logger.warning("whatsapp_send_skipped", error=str(e))

    return _on_message_approved


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
    app.state.contact_store = ContactStoreClient(settings.contact_store_url)
    app.state.tenant_client = TenantClient(settings.tenant_service_url, get_redis())
    app.state.encryptor = SecretEncryptor(settings.whatsapp_encryption_key)
    app.state.window = SessionWindowChecker(get_redis(), window_hours=settings.session_window_hours)

    subscriber = Subscriber(
        nats_conn.js,
        stream="BRIEFS",
        durable=settings.nats_durable_name,
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
        await app.state.tenant_client.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="WhatsApp Sender", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(whatsapp_router)

    return app


app = create_app()
