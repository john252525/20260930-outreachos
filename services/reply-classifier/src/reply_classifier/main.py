"""Reply-classifier FastAPI application."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
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
from reply_classifier.api.routes import router as replies_router
from reply_classifier.classifier.composite import CompositeClassifier
from reply_classifier.classifier.llm_classifier import LLMClassifier
from reply_classifier.classifier.rule_fallback import RuleBasedClassifier
from reply_classifier.clients.composer_client import ComposerClient
from reply_classifier.clients.contact_store_client import ContactStoreClient
from reply_classifier.config import Settings
from reply_classifier.llm.client import LLMClient
from reply_classifier.repository import ReplyRepository
from reply_classifier.service import ReplyService

logger = structlog.get_logger()


class ReplyNackError(Exception):
    """Signals a retryable failure — causes a delayed nack."""


def _make_handler(app: FastAPI) -> Callable[[EventEnvelope[Any]], Awaitable[None]]:
    async def _on_reply_received(envelope: EventEnvelope[Any]) -> None:
        tenant_id = envelope.tenant_id
        r = envelope.payload.reply
        received_at = None
        if getattr(r, "received_at", None):
            received_at = datetime.fromisoformat(str(r.received_at).replace("Z", "+00:00"))
        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            svc = ReplyService(
                repo=ReplyRepository(session),
                classifier=app.state.classifier,
                composer_client=app.state.composer,
                contact_store_client=app.state.contact_store,
                publisher=app.state.publisher,
                settings=app.state.settings,
            )
            try:
                await svc.process_incoming_reply(
                    tenant_id=tenant_id,
                    message_id=UUID(str(r.message_id)),
                    from_email=r.from_email,
                    from_name=r.from_name,
                    subject=r.subject,
                    body=r.body,
                    received_at=received_at or datetime.now(UTC),
                    in_reply_to=r.in_reply_to,
                    references=r.references,
                    message_id_header=r.message_id_header,
                    trace_id=envelope.trace_id,
                )
            except Exception as e:
                logger.exception("reply_processing_failed", error=str(e))
                raise ReplyNackError(str(e)) from e

    return _on_reply_received


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(level=settings.log_level, service_name=settings.service_name)

    init_engine(settings.database_url)
    init_redis(settings.redis_url)

    nats_conn = NATSConnection(settings.nats_url, name=settings.service_name)
    await nats_conn.connect()

    llm = LLMClient(settings)
    classifier = CompositeClassifier(
        RuleBasedClassifier(),
        LLMClassifier(llm, max_body_length=settings.max_body_length),
        min_confidence=settings.min_confidence,
    )

    app.state.settings = settings
    app.state.nats = nats_conn
    app.state.publisher = Publisher(nats_conn.js, producer=f"{settings.service_name}/0.1.0")
    app.state.composer = ComposerClient(settings.composer_service_url)
    app.state.contact_store = ContactStoreClient(settings.contact_store_url)
    app.state.llm = llm
    app.state.classifier = classifier

    subscriber = Subscriber(
        nats_conn.js,
        stream="BRIEFS",
        durable=settings.nats_durable_name,
        filter_subjects=["reply.received.*"],
        handler=_make_handler(app),
        batch_size=5,
        fetch_timeout=5.0,
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
        await app.state.contact_store.close()
        await llm.close()
        await nats_conn.close()
        await close_redis()
        await dispose_engine()
        logger.info("service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Reply Classifier", version="0.1.0", lifespan=lifespan)

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(TraceMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(replies_router)

    return app


app = create_app()
