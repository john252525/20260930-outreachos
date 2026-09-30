"""FastAPI dependencies for tenant-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from nats_client.publisher import Publisher
from tenant_service.repository import TenantRepository
from tenant_service.service import TenantService


async def get_service(request: Request) -> AsyncIterator[TenantService]:
    tenant_id = get_tenant_id()
    session = async_session_factory()
    async with session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        repo = TenantRepository(session)
        yield TenantService(repo)


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher  # type: ignore[no-any-return]
