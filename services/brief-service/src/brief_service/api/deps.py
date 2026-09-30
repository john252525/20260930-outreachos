"""FastAPI dependencies for brief-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from brief_service.repository import BriefRepository
from brief_service.service import BriefService
from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from nats_client.publisher import Publisher


async def get_service(request: Request) -> AsyncIterator[BriefService]:
    tenant_id = get_tenant_id()
    session = async_session_factory()
    async with session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        repo = BriefRepository(session)
        yield BriefService(
            repo=repo,
            llm=request.app.state.llm,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher  # type: ignore[no-any-return]
