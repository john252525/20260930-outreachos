"""User routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from common.context import get_tenant_id
from common.errors import ValidationError
from users_service.api.deps import get_service
from users_service.auth.deps import require_role
from users_service.schemas import MembershipRead, UserRead
from users_service.service import UserService

router = APIRouter(tags=["users"])


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID,
    svc: UserService = Depends(get_service),
    _: dict[str, Any] = Depends(require_role("admin", "manager")),
) -> UserRead:
    user = await svc.get_user(user_id)
    return UserRead.model_validate(user)


@router.get("/tenant-users", response_model=list[MembershipRead])
async def list_tenant_users(
    svc: UserService = Depends(get_service),
    _: dict[str, Any] = Depends(require_role("admin", "manager")),
) -> list[MembershipRead]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    memberships = await svc.list_tenant_users(tenant_id)
    return [MembershipRead.model_validate(m) for m in memberships]


@router.post("/tenant-users/{user_id}/role", response_model=MembershipRead)
async def update_role(
    user_id: UUID,
    role: str,
    user: dict[str, Any] = Depends(require_role("admin")),
    svc: UserService = Depends(get_service),
) -> MembershipRead:
    member = await svc.update_role(
        tenant_id=UUID(user["tenant_id"]),
        user_id=user_id,
        role=role,
        actor_id=UUID(user["sub"]),
    )
    return MembershipRead.model_validate(member)
