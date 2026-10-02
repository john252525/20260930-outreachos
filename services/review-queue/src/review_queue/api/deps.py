"""FastAPI dependencies for review-queue."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from review_queue.repository import ReviewItemRepository
from review_queue.service import ReviewQueueService


async def get_service(request: Request) -> AsyncIterator[ReviewQueueService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield ReviewQueueService(
            repo=ReviewItemRepository(session),
            composer=request.app.state.composer,
            publisher=request.app.state.publisher,
        )
