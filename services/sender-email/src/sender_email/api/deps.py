"""FastAPI dependencies for sender-email."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from common.redis import get_redis
from db.rls import set_tenant_context
from db.session import async_session_factory
from sender_email.rampup.limiter import RampUpLimiter
from sender_email.repository import SenderRepository
from sender_email.service import SenderService


async def get_service(request: Request) -> AsyncIterator[SenderService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield SenderService(
            repo=SenderRepository(session),
            composer=request.app.state.composer,
            contact_store=request.app.state.contact_store,
            encryptor=request.app.state.encryptor,
            limiter=RampUpLimiter(get_redis()),
            account_manager=request.app.state.account_manager,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
