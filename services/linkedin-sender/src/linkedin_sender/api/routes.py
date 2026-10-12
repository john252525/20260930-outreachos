"""HTTP routes for linkedin-sender."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.context import get_tenant_id
from common.errors import ValidationError
from linkedin_sender.api.deps import get_service
from linkedin_sender.schemas import (
    AccountCreate,
    AccountRead,
    AttemptRead,
    SolveCaptchaRequest,
)
from linkedin_sender.service import LinkedInSenderService

router = APIRouter(tags=["linkedin"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    svc: LinkedInSenderService = Depends(get_service),
) -> AccountRead:
    account = await svc.create_account(tenant_id=_tenant(), data=data.model_dump())
    return AccountRead.model_validate(account)


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    svc: LinkedInSenderService = Depends(get_service),
) -> list[AccountRead]:
    accounts = await svc.list_accounts(_tenant())
    return [AccountRead.model_validate(a) for a in accounts]


@router.post("/accounts/{account_id}/verify", response_model=AccountRead)
async def verify_account(
    account_id: UUID,
    svc: LinkedInSenderService = Depends(get_service),
) -> AccountRead:
    return AccountRead.model_validate(await svc.verify_account(account_id))


@router.post("/accounts/{account_id}/pause", response_model=AccountRead)
async def pause_account(
    account_id: UUID,
    svc: LinkedInSenderService = Depends(get_service),
) -> AccountRead:
    return AccountRead.model_validate(await svc.set_account_status(account_id, "paused"))


@router.post("/accounts/{account_id}/resume", response_model=AccountRead)
async def resume_account(
    account_id: UUID,
    svc: LinkedInSenderService = Depends(get_service),
) -> AccountRead:
    return AccountRead.model_validate(await svc.set_account_status(account_id, "active"))


@router.post("/accounts/{account_id}/solve-captcha", response_model=AccountRead)
async def solve_captcha(
    account_id: UUID,
    data: SolveCaptchaRequest,
    svc: LinkedInSenderService = Depends(get_service),
) -> AccountRead:
    return AccountRead.model_validate(await svc.solve_captcha(account_id))


@router.get("/attempts", response_model=list[AttemptRead])
async def list_attempts(
    limit: int = Query(50, ge=1, le=200),
    svc: LinkedInSenderService = Depends(get_service),
) -> list[AttemptRead]:
    attempts = await svc.list_attempts(_tenant(), limit=limit)
    return [AttemptRead.model_validate(a) for a in attempts]
