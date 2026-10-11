"""FastAPI dependencies for reply-classifier."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from reply_classifier.repository import ReplyRepository
from reply_classifier.service import ReplyService


async def get_service(request: Request) -> AsyncIterator[ReplyService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield ReplyService(
            repo=ReplyRepository(session),
            classifier=request.app.state.classifier,
            composer_client=request.app.state.composer,
            contact_store_client=request.app.state.contact_store,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
