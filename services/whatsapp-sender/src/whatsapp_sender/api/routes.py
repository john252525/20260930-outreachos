"""HTTP routes for whatsapp-sender."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id
from common.errors import ValidationError
from whatsapp_sender.api.deps import get_service
from whatsapp_sender.schemas import (
    AccountCreate,
    AccountRead,
    AttemptRead,
    TemplateCreate,
    TemplateRead,
    WebhookMessage,
)
from whatsapp_sender.service import WhatsAppSenderService

router = APIRouter(tags=["whatsapp"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate, svc: WhatsAppSenderService = Depends(get_service)
) -> AccountRead:
    account = await svc.create_account(tenant_id=_tenant(), data=data.model_dump())
    return AccountRead.model_validate(account)


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    svc: WhatsAppSenderService = Depends(get_service),
) -> list[AccountRead]:
    return [AccountRead.model_validate(a) for a in await svc.list_accounts(_tenant())]


@router.post("/accounts/{account_id}/verify", response_model=AccountRead)
async def verify_account(
    account_id: UUID, svc: WhatsAppSenderService = Depends(get_service)
) -> AccountRead:
    return AccountRead.model_validate(await svc.verify_account(account_id))


@router.post("/templates", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate, svc: WhatsAppSenderService = Depends(get_service)
) -> TemplateRead:
    template = await svc.create_template(tenant_id=_tenant(), data=data.model_dump())
    return TemplateRead.model_validate(template)


@router.get("/templates", response_model=list[TemplateRead])
async def list_templates(
    svc: WhatsAppSenderService = Depends(get_service),
) -> list[TemplateRead]:
    return [TemplateRead.model_validate(t) for t in await svc.list_templates(_tenant())]


@router.get("/attempts", response_model=list[AttemptRead])
async def list_attempts(
    limit: int = Query(50, ge=1, le=200),
    svc: WhatsAppSenderService = Depends(get_service),
) -> list[AttemptRead]:
    return [AttemptRead.model_validate(a) for a in await svc.list_attempts(_tenant(), limit=limit)]


@router.post("/webhooks/inbound")
async def inbound_webhook(
    data: WebhookMessage, svc: WhatsAppSenderService = Depends(get_service)
) -> dict[str, str]:
    await svc.mark_inbound(tenant_id=data.tenant_id, phone=data.from_phone)
    return {"status": "ok"}
