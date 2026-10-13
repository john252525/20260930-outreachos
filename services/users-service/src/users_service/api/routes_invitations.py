"""Invitation routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from users_service.api.deps import get_service
from users_service.auth.deps import get_current_user, require_role
from users_service.schemas import InvitationRead, InviteRequest, MembershipRead
from users_service.service import UserService

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("", response_model=InvitationRead, status_code=status.HTTP_201_CREATED)
async def invite(
    data: InviteRequest,
    user: dict[str, Any] = Depends(require_role("admin")),
    svc: UserService = Depends(get_service),
) -> InvitationRead:
    invitation = await svc.invite(
        tenant_id=UUID(user["tenant_id"]),
        invited_by=UUID(user["sub"]),
        email=data.email,
        role=data.role,
    )
    return InvitationRead.model_validate(invitation)


@router.get("", response_model=list[InvitationRead])
async def list_invitations(
    user: dict[str, Any] = Depends(require_role("admin", "manager")),
    svc: UserService = Depends(get_service),
) -> list[InvitationRead]:
    invitations = await svc.list_invitations(UUID(user["tenant_id"]))
    return [InvitationRead.model_validate(i) for i in invitations]


@router.post("/accept/{token}", response_model=MembershipRead)
async def accept_invitation(
    token: str,
    user: dict[str, Any] = Depends(get_current_user),
    svc: UserService = Depends(get_service),
) -> MembershipRead:
    membership = await svc.accept_invitation(token=token, user_id=UUID(user["sub"]))
    return MembershipRead.model_validate(membership)
