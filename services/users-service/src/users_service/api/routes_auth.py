"""Auth routes: register / login / switch-tenant / logout / password-reset."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from users_service.api.deps import get_service
from users_service.auth.deps import get_current_user, get_token_service
from users_service.auth.tokens import TokenService
from users_service.schemas import (
    AvailableTenant,
    LoginRequest,
    LoginResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    SwitchTenantRequest,
    UserMe,
)
from users_service.service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    svc: UserService = Depends(get_service),
    tokens: TokenService = Depends(get_token_service),
) -> RegisterResponse:
    user, tenant_id = await svc.register(
        email=data.email,
        password=data.password,
        display_name=data.display_name,
        company_name=data.company_name,
        ip=_ip(request),
    )
    token, expires_at = tokens.create_access_token(
        user_id=user.id, email=user.email, tenant_id=tenant_id, role="admin"
    )
    return RegisterResponse(
        user_id=user.id, tenant_id=tenant_id, access_token=token, expires_at=expires_at
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    svc: UserService = Depends(get_service),
    tokens: TokenService = Depends(get_token_service),
) -> LoginResponse:
    user = await svc.authenticate(email=data.email, password=data.password, ip=_ip(request))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    memberships = await svc.list_memberships(user.id)
    if not memberships:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant memberships")

    if data.tenant_id:
        membership = next((m for m in memberships if m.tenant_id == data.tenant_id), None)
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
    else:
        membership = memberships[0]

    token, expires_at = tokens.create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=membership.tenant_id,
        role=membership.role,
    )
    return LoginResponse(
        user_id=user.id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        display_name=user.display_name,
        access_token=token,
        expires_at=expires_at,
        available_tenants=[AvailableTenant(id=str(m.tenant_id), role=m.role) for m in memberships],
    )


@router.post("/switch-tenant", response_model=LoginResponse)
async def switch_tenant(
    data: SwitchTenantRequest,
    user: dict[str, Any] = Depends(get_current_user),
    svc: UserService = Depends(get_service),
    tokens: TokenService = Depends(get_token_service),
) -> LoginResponse:
    user_id = UUID(user["sub"])
    membership = await svc.get_membership(data.tenant_id, user_id)
    token, expires_at = tokens.create_access_token(
        user_id=user_id,
        email=user["email"],
        tenant_id=membership.tenant_id,
        role=membership.role,
    )
    memberships = await svc.list_memberships(user_id)
    return LoginResponse(
        user_id=user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        display_name=user.get("email", ""),
        access_token=token,
        expires_at=expires_at,
        available_tenants=[AvailableTenant(id=str(m.tenant_id), role=m.role) for m in memberships],
    )


@router.get("/me", response_model=UserMe)
async def me(user: dict[str, Any] = Depends(get_current_user)) -> UserMe:
    return UserMe(
        id=UUID(user["sub"]),
        email=user["email"],
        display_name=user.get("email", ""),
        status="active",
        tenant_id=user["tenant_id"],
        role=user["role"],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    return None


@router.post("/password-reset-request", status_code=status.HTTP_202_ACCEPTED)
async def password_reset_request(
    data: PasswordResetRequest,
) -> None:
    # MVP: no-op (transactional email deferred). Always 202 to avoid user enumeration.
    return None


@router.post("/password-reset-confirm", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset_confirm(data: PasswordResetConfirm) -> None:
    return None
