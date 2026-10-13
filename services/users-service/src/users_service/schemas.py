"""API schemas for users-service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1)
    tenant_id: UUID | None = None


class SwitchTenantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID


class AvailableTenant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    role: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: UUID
    tenant_id: UUID
    role: str
    display_name: str
    access_token: str
    expires_at: datetime
    available_tenants: list[AvailableTenant] = Field(default_factory=list)


class RegisterResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: UUID
    tenant_id: UUID
    access_token: str
    expires_at: datetime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)
    id: UUID
    email: str
    display_name: str
    status: str
    email_verified: bool
    last_login_at: datetime | None
    created_at: datetime


class UserMe(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    email: str
    display_name: str
    status: str
    tenant_id: str
    role: str


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    user_id: UUID
    role: str
    is_owner: bool
    is_active: bool
    accepted_at: datetime | None


class InviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    role: str = Field(default="viewer", pattern="^(admin|manager|viewer)$")


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    new_password: str = Field(min_length=8, max_length=200)


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    tenant_id: UUID | None
    user_id: UUID | None
    actor_type: str
    action: str
    resource_type: str
    resource_id: UUID | None
    result: str
    ip_address: str | None
    occurred_at: datetime
    changes: dict[str, Any]
