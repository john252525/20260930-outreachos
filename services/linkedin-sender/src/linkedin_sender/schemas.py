"""API schemas for linkedin-sender."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: str
    user_id: str | None = None
    proxy_url: str | None = None
    proxy_type: str | None = None
    cookies: str | None = None
    user_agent: str | None = None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    tenant_id: UUID
    user_id: str | None
    email: str
    status: str
    proxy_url: str | None
    daily_sent_today: int
    daily_limit_current: int
    weekly_limit_current: int
    last_verified_at: datetime | None
    last_error: str | None
    ban_detected_at: datetime | None
    ban_reason: str | None
    created_at: datetime
    updated_at: datetime


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    message_id: UUID
    account_id: UUID | None
    status: str
    to_handle: str
    provider_message_id: str | None
    error: str | None
    sent_at: datetime | None
    created_at: datetime


class SolveCaptchaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolved: bool = True
