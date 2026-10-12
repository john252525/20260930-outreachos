"""ORM models for telegram-sender."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TelegramAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "telegram_accounts"

    account_type: Mapped[str] = mapped_column(String(16), nullable=False)  # bot | mtproto

    bot_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    api_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_hash_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    session_string_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    hourly_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    warmup_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    flood_wait_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_telegram_accounts_phone"),
        UniqueConstraint("tenant_id", "bot_username", name="uq_telegram_accounts_bot"),
        Index("ix_telegram_accounts_tenant_status", "tenant_id", "status"),
    )


class TelegramSendAttempt(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "telegram_send_attempts"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("telegram_accounts.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    to_handle: Mapped[str] = mapped_column(String(128), nullable=False)
    to_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    telegram_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    flood_wait_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_telegram_attempts_tenant_message", "tenant_id", "message_id"),
        Index("ix_telegram_attempts_tenant_status", "tenant_id", "status"),
    )
