"""API schemas for sender-email."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SenderAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    display_name: str | None = None
    user_id: str | None = None

    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = 465
    smtp_use_ssl: bool = True
    smtp_username: str = Field(min_length=1, max_length=320)
    smtp_password: str = Field(min_length=1)

    imap_host: str | None = None
    imap_port: int = 993
    imap_use_ssl: bool = True
    imap_username: str | None = None
    imap_password: str | None = None


class SenderAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    tenant_id: UUID
    user_id: str
    email: str
    display_name: str | None
    status: str
    smtp_host: str
    smtp_port: int
    last_verified_at: datetime | None
    last_error: str | None
    daily_limit_current: int
    hourly_limit_current: int
    warmup_started_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SendAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    tenant_id: UUID
    message_id: UUID
    sender_account_id: UUID | None
    status: str
    to_email: str
    from_email: str
    smtp_message_id: str | None
    error: str | None
    sent_at: datetime | None
    created_at: datetime
