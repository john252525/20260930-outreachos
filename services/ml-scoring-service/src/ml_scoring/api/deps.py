"""FastAPI dependencies for ml-scoring."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from ml_scoring.repository import FeatureRepository
from ml_scoring.service import ScoringService


async def get_service(request: Request) -> AsyncIterator[ScoringService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield ScoringService(
            repo=FeatureRepository(session),
            settings=request.app.state.settings,
        )
