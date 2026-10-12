"""ORM models for linkedin-sender."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LinkedInAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "linkedin_accounts"

    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    cookies_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    proxy_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    proxy_type: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # unverified | active | paused | captcha_required | banned | error
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified", index=True
    )

    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    weekly_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    warmup_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    ban_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_linkedin_accounts_tenant_email"),
        Index("ix_linkedin_accounts_tenant_status", "tenant_id", "status"),
    )


class LinkedInSendAttempt(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "linkedin_send_attempts"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("linkedin_accounts.id", ondelete="SET NULL"), nullable=True
    )

    # pending | sent | failed | captcha_required | banned | skipped
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    to_handle: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_linkedin_attempts_tenant_message", "tenant_id", "message_id"),
        Index("ix_linkedin_attempts_tenant_status", "tenant_id", "status"),
    )
