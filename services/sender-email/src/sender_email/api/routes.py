"""HTTP routes for sender-email."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from common.context import get_tenant_id
from common.errors import ValidationError
from sender_email.api.deps import get_service
from sender_email.schemas import SenderAccountCreate, SenderAccountRead
from sender_email.service import SenderService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=SenderAccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: SenderAccountCreate,
    request: Request,
    svc: SenderService = Depends(get_service),
) -> SenderAccountRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    user_id = data.user_id or request.headers.get("X-User-Id", "anonymous")
    account = await svc.create_account(tenant_id=tenant_id, data=data.model_dump(), user_id=user_id)
    return SenderAccountRead.model_validate(account)


@router.get("", response_model=list[SenderAccountRead])
async def list_accounts(
    svc: SenderService = Depends(get_service),
) -> list[SenderAccountRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    accounts = await svc.list_accounts(tenant_id)
    return [SenderAccountRead.model_validate(a) for a in accounts]


@router.post("/{account_id}/verify", response_model=SenderAccountRead)
async def verify_account(
    account_id: UUID,
    svc: SenderService = Depends(get_service),
) -> SenderAccountRead:
    account = await svc.verify_account(account_id)
    return SenderAccountRead.model_validate(account)


@router.post("/{account_id}/pause", response_model=SenderAccountRead)
async def pause_account(
    account_id: UUID,
    svc: SenderService = Depends(get_service),
) -> SenderAccountRead:
    account = await svc.set_account_status(account_id, "paused")
    return SenderAccountRead.model_validate(account)


@router.post("/{account_id}/resume", response_model=SenderAccountRead)
async def resume_account(
    account_id: UUID,
    svc: SenderService = Depends(get_service),
) -> SenderAccountRead:
    account = await svc.set_account_status(account_id, "active")
    return SenderAccountRead.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    svc: SenderService = Depends(get_service),
) -> None:
    await svc.delete_account(account_id)
