"""FastAPI dependencies for campaign-service."""

from collections.abc import AsyncIterator

from fastapi import Request

from campaign_service.repository import CampaignRepository
from campaign_service.service import CampaignService
from common.context import get_tenant_id
from db.rls import set_tenant_context
from db.session import async_session_factory


async def get_service(request: Request) -> AsyncIterator[CampaignService]:
    tenant_id = get_tenant_id()
    async with async_session_factory() as session, session.begin():
        if tenant_id is not None:
            await set_tenant_context(session, tenant_id)
        yield CampaignService(
            repo=CampaignRepository(session),
            analytics=request.app.state.analytics,
            settings=request.app.state.settings,
        )
