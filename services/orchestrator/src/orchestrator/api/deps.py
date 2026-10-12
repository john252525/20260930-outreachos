"""FastAPI dependencies for orchestrator."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from orchestrator.repository import FlowRepository
from orchestrator.service import OrchestratorService


async def get_service(request: Request) -> AsyncIterator[OrchestratorService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield OrchestratorService(
            repo=FlowRepository(session),
            composer=request.app.state.composer,
            contact_store=request.app.state.contact_store,
            icp_client=request.app.state.icp_client,
            settings=request.app.state.settings,
        )
