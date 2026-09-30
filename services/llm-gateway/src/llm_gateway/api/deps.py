"""FastAPI dependencies for llm-gateway."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from common.errors import AppError
from common.redis import get_redis
from db.rls import set_tenant_context
from db.session import async_session_factory, get_session_factory
from llm_gateway.service import LLMGatewayService


async def get_service(request: Request) -> AsyncIterator[LLMGatewayService]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise AppError("X-Tenant-ID required", code="missing_tenant", status_code=400)

    session = async_session_factory()
    async with session, session.begin():
        await set_tenant_context(session, tenant_id)
        yield LLMGatewayService(
            registry=request.app.state.registry,
            session=session,
            redis=get_redis(),
            langfuse=request.app.state.langfuse,
            cache_ttl=request.app.state.settings.llm_cache_ttl,
            tenant_id=tenant_id,
            session_factory=get_session_factory(),
        )
