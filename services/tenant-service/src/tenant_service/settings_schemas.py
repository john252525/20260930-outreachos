"""Schemas for tenant settings."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    tenant_id: UUID
    auto_brief_to_icp: bool
    auto_icp_to_sourcing: bool
    auto_contacts_to_drafts: bool
    auto_drafts_to_review: bool
    auto_approved_to_send: bool
    auto_revision_enabled: bool
    default_sources: list[str]
    default_limit_per_source: int
    max_sources_per_search: int
    default_channel: str
    default_max_contacts_per_flow: int
    default_sender_daily_limit: int
    email_enabled: bool
    telegram_enabled: bool
    linkedin_enabled: bool
    whatsapp_enabled: bool
    alert_reply_rate_threshold: float
    alert_bounce_rate_threshold: float
    quota_llm_tokens_month: int | None
    quota_messages_day: int | None
    quota_contacts_max: int | None
    branding: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TenantSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_brief_to_icp: bool | None = None
    auto_icp_to_sourcing: bool | None = None
    auto_contacts_to_drafts: bool | None = None
    auto_drafts_to_review: bool | None = None
    auto_approved_to_send: bool | None = None
    auto_revision_enabled: bool | None = None
    default_sources: list[str] | None = None
    default_limit_per_source: int | None = None
    max_sources_per_search: int | None = None
    default_channel: str | None = None
    default_max_contacts_per_flow: int | None = None
    default_sender_daily_limit: int | None = None
    email_enabled: bool | None = None
    telegram_enabled: bool | None = None
    linkedin_enabled: bool | None = None
    whatsapp_enabled: bool | None = None
    alert_reply_rate_threshold: float | None = None
    alert_bounce_rate_threshold: float | None = None
    quota_llm_tokens_month: int | None = None
    quota_messages_day: int | None = None
    quota_contacts_max: int | None = None
    branding: dict[str, Any] | None = None
