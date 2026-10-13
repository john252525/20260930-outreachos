"""API schemas for whatsapp-sender."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(pattern="^(gupshup|twilio|360dialog)$")
    phone_number: str
    provider_account_id: str
    api_key: str
    display_name: str | None = None
    user_id: str | None = None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    tenant_id: UUID
    provider: str
    phone_number: str
    display_name: str | None
    status: str
    daily_sent_today: int
    daily_limit_current: int
    last_verified_at: datetime | None
    last_error: str | None
    created_at: datetime


class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    language: str = "ru"
    category: str = Field(pattern="^(marketing|utility|authentication)$")
    body_template: str
    variables_count: int = 0


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    name: str
    language: str
    category: str
    status: str
    body_template: str
    variables_count: int
    created_at: datetime


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    message_id: UUID
    account_id: UUID | None
    status: str
    to_phone: str
    provider_message_id: str | None
    error: str | None
    sent_at: datetime | None
    created_at: datetime


class WebhookMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tenant_id: UUID
    from_phone: str
