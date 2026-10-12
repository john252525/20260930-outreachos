"""FastAPI dependencies for linkedin-sender."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from common.redis import get_redis
from db.rls import set_tenant_context
from db.session import async_session_factory
from linkedin_sender.rampup import LinkedInRateLimiter
from linkedin_sender.repository import LinkedInRepository
from linkedin_sender.service import LinkedInSenderService


async def get_service(request: Request) -> AsyncIterator[LinkedInSenderService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield LinkedInSenderService(
            repo=LinkedInRepository(session),
            composer=request.app.state.composer,
            contact_store=request.app.state.contact_store,
            tenant_client=request.app.state.tenant_client,
            encryptor=request.app.state.encryptor,
            limiter=LinkedInRateLimiter(get_redis()),
            scheduler=request.app.state.scheduler,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
