"""FastAPI dependencies for whatsapp-sender."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory
from whatsapp_sender.repository import WhatsAppRepository
from whatsapp_sender.service import WhatsAppSenderService


async def get_service(request: Request) -> AsyncIterator[WhatsAppSenderService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield WhatsAppSenderService(
            repo=WhatsAppRepository(session),
            composer=request.app.state.composer,
            contact_store=request.app.state.contact_store,
            tenant_client=request.app.state.tenant_client,
            encryptor=request.app.state.encryptor,
            window=request.app.state.window,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
