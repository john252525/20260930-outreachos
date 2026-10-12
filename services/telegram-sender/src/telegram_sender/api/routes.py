"""HTTP routes for telegram-sender."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id
from common.errors import ValidationError
from telegram_sender.api.deps import get_service
from telegram_sender.schemas import AccountCreate, AccountRead, AttemptRead
from telegram_sender.service import TelegramSenderService

router = APIRouter(tags=["telegram"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    svc: TelegramSenderService = Depends(get_service),
) -> AccountRead:
    account = await svc.create_account(tenant_id=_tenant(), data=data.model_dump())
    return AccountRead.model_validate(account)


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    svc: TelegramSenderService = Depends(get_service),
) -> list[AccountRead]:
    accounts = await svc.list_accounts(_tenant())
    return [AccountRead.model_validate(a) for a in accounts]


@router.post("/accounts/{account_id}/verify", response_model=AccountRead)
async def verify_account(
    account_id: UUID,
    svc: TelegramSenderService = Depends(get_service),
) -> AccountRead:
    account = await svc.verify_account(account_id)
    return AccountRead.model_validate(account)


@router.post("/accounts/{account_id}/pause", response_model=AccountRead)
async def pause_account(
    account_id: UUID,
    svc: TelegramSenderService = Depends(get_service),
) -> AccountRead:
    account = await svc.set_account_status(account_id, "paused")
    return AccountRead.model_validate(account)


@router.post("/accounts/{account_id}/resume", response_model=AccountRead)
async def resume_account(
    account_id: UUID,
    svc: TelegramSenderService = Depends(get_service),
) -> AccountRead:
    account = await svc.set_account_status(account_id, "active")
    return AccountRead.model_validate(account)


@router.get("/attempts", response_model=list[AttemptRead])
async def list_attempts(
    limit: int = Query(50, ge=1, le=200),
    svc: TelegramSenderService = Depends(get_service),
) -> list[AttemptRead]:
    attempts = await svc.list_attempts(_tenant(), limit=limit)
    return [AttemptRead.model_validate(a) for a in attempts]
