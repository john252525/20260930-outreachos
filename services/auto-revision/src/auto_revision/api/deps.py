"""FastAPI dependencies for auto-revision."""

from collections.abc import AsyncIterator

from fastapi import Request

from auto_revision.repository import RevisionRepository
from auto_revision.service import RevisionService
from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory


async def get_service(request: Request) -> AsyncIterator[RevisionService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield RevisionService(
            repo=RevisionRepository(session),
            analyzer=request.app.state.analyzer,
            advisor=request.app.state.advisor,
            revisor=request.app.state.revisor,
            composer=request.app.state.composer,
            experiments=request.app.state.experiments,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
