"""ORM models for tenant-service."""

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import (
    MetadataMixin,
    SchemaVersionMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")

    quota_llm_tokens_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_messages_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_contacts_max: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TenantSettings(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Per-tenant configuration. Defaults live in code, not the DB."""

    __tablename__ = "tenant_settings"

    # Automation
    auto_brief_to_icp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_icp_to_sourcing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_contacts_to_drafts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_drafts_to_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_approved_to_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_revision_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Sourcing
    default_sources: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    default_limit_per_source: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    max_sources_per_search: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Outreach
    default_channel: Mapped[str] = mapped_column(String(16), nullable=False, default="email")
    default_max_contacts_per_flow: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    default_sender_daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Channels
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linkedin_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Alerts
    alert_reply_rate_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    alert_bounce_rate_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    # Quotas
    quota_llm_tokens_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_messages_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_contacts_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Branding (UI)
    branding: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
