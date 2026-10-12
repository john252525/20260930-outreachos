"""FastAPI dependencies for composer-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from common.context import get_tenant_id
from composer_service.overrides import TemplateOverrideRepository
from composer_service.repository import MessageRepository
from composer_service.service import ComposerService
from db.rls import set_tenant_context
from db.session import async_session_factory


async def get_service(request: Request) -> AsyncIterator[ComposerService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield ComposerService(
            repo=MessageRepository(session),
            override_repo=TemplateOverrideRepository(session),
            contact_store=request.app.state.contact_store,
            experiments_client=request.app.state.experiments_client,
            brief_client=request.app.state.brief_client,
            icp_client=request.app.state.icp_client,
            template_registry=request.app.state.template_registry,
            personalizer=request.app.state.personalizer,
            fact_checker=request.app.state.fact_checker,
            publisher=request.app.state.publisher,
            settings=request.app.state.settings,
        )
