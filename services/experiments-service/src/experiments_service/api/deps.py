"""FastAPI dependencies for experiments-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from experiments_service.repository import ExperimentRepository
from experiments_service.service import ExperimentService


async def get_service(request: Request) -> AsyncIterator[ExperimentService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield ExperimentService(
            repo=ExperimentRepository(session),
            analytics=request.app.state.analytics,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
