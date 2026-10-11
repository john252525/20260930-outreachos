"""ORM models for sender-email."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import MetadataMixin, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SenderAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, MetadataMixin):
    """A connected sender mailbox."""

    __tablename__ = "sender_accounts"

    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=465)
    smtp_use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    smtp_username: Mapped[str] = mapped_column(String(320), nullable=False)
    smtp_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    imap_use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    imap_username: Mapped[str] = mapped_column(String(320), nullable=False)
    imap_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified", index=True
    )

    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    hourly_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    warmup_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    spf_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dkim_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dmarc_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dns_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    daily_limit_max: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    hourly_limit_max: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_sender_accounts_tenant_email"),
        Index("ix_sender_accounts_tenant_status", "tenant_id", "status"),
    )


class SendAttempt(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """History of send attempts."""

    __tablename__ = "send_attempts"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    sender_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sender_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    from_email: Mapped[str] = mapped_column(String(320), nullable=False)

    smtp_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    bounce_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bounce_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    __table_args__ = (
        Index("ix_send_attempts_tenant_message", "tenant_id", "message_id"),
        Index("ix_send_attempts_tenant_status", "tenant_id", "status"),
        Index("ix_send_attempts_sent_at", "tenant_id", "sent_at"),
    )
