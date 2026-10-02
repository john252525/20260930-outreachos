"""FastAPI dependencies for sourcing-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from sourcing_service.repository import SearchJobRepository
from sourcing_service.service import SearchOrchestrator


async def get_service(request: Request) -> AsyncIterator[SearchOrchestrator]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield SearchOrchestrator(
            repo=SearchJobRepository(session),
            icp_client=request.app.state.icp_client,
            contact_store=request.app.state.contact_store,
            registry=request.app.state.connector_registry,
            normalizer=request.app.state.normalizer,
            scorer=request.app.state.scorer,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
            running_tasks=request.app.state.running_tasks,
        )
