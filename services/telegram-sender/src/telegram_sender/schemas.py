"""API schemas for telegram-sender."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_type: str = Field(pattern="^(bot|mtproto)$")
    display_name: str | None = None
    user_id: str | None = None
    # bot
    bot_token: str | None = None
    bot_username: str | None = None
    # mtproto
    api_id: int | None = None
    api_hash: str | None = None
    phone: str | None = None
    session_string: str | None = None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    tenant_id: UUID
    account_type: str
    bot_username: str | None
    phone: str | None
    display_name: str | None
    user_id: str | None
    status: str
    daily_sent_today: int
    daily_limit_current: int
    hourly_limit_current: int
    flood_wait_until: datetime | None
    last_error: str | None
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    message_id: UUID
    account_id: UUID | None
    status: str
    to_handle: str
    telegram_message_id: str | None
    error: str | None
    flood_wait_seconds: int | None
    sent_at: datetime | None
    created_at: datetime
