"""ORM models for whatsapp-sender."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class WhatsAppAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "whatsapp_accounts"

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified", index=True
    )

    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_number", name="uq_whatsapp_accounts_phone"),
        Index("ix_whatsapp_accounts_tenant_status", "tenant_id", "status"),
    )


class WhatsAppTemplate(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "whatsapp_templates"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_template_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "language", name="uq_whatsapp_templates"),
    )


class WhatsAppSendAttempt(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "whatsapp_send_attempts"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("whatsapp_accounts.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    to_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[UUID | None] = mapped_column(nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_whatsapp_attempts_tenant_message", "tenant_id", "message_id"),
        Index("ix_whatsapp_attempts_tenant_status", "tenant_id", "status"),
    )
