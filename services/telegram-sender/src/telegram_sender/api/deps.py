"""FastAPI dependencies for telegram-sender."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from common.redis import get_redis
from db.rls import set_tenant_context
from db.session import async_session_factory
from telegram_sender.rampup import TelegramRateLimiter
from telegram_sender.repository import TelegramRepository
from telegram_sender.service import TelegramSenderService


async def get_service(request: Request) -> AsyncIterator[TelegramSenderService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield TelegramSenderService(
            repo=TelegramRepository(session),
            composer=request.app.state.composer,
            contact_store=request.app.state.contact_store,
            encryptor=request.app.state.encryptor,
            limiter=TelegramRateLimiter(get_redis()),
            scheduler=request.app.state.scheduler,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
