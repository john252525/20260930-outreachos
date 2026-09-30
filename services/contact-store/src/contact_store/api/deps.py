"""FastAPI dependencies for contact-store."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from contact_store.repository import CompanyRepository, ContactRepository
from contact_store.service import CompanyService, ContactService
from contact_store.stoplist import StopList
from db.rls import set_tenant_context
from db.session import async_session_factory
from nats_client.publisher import Publisher


async def get_company_service(request: Request) -> AsyncIterator[CompanyService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield CompanyService(
            repo=CompanyRepository(session),
            publisher=request.app.state.publisher,
        )


async def get_contact_service(request: Request) -> AsyncIterator[ContactService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield ContactService(
            repo=ContactRepository(session),
            company_repo=CompanyRepository(session),
            stoplist=StopList(session),
            publisher=request.app.state.publisher,
        )


async def get_stoplist(request: Request) -> AsyncIterator[StopList]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield StopList(session)


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher  # type: ignore[no-any-return]
