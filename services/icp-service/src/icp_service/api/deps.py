"""FastAPI dependencies for icp-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from icp_service.repository import ICPRepository
from icp_service.service import ICPService


async def get_service(request: Request) -> AsyncIterator[ICPService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield ICPService(
            repo=ICPRepository(session),
            brief_client=request.app.state.brief_client,
            llm=request.app.state.llm,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
