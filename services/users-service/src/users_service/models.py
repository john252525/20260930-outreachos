"""ORM models for users-service."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.mixins import MetadataMixin, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import UUID7, generate_uuid7


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """Global user (not tenant-scoped). A user may belong to several tenants."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verification_token: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    password_reset_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["UserTenant"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserTenant.user_id",
    )


class UserTenant(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """user ↔ tenant membership with role."""

    __tablename__ = "user_tenants"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer", index=True)

    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    invited_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(
        back_populates="memberships", foreign_keys=[user_id]
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_user_tenants"),
        Index("ix_user_tenants_tenant_role", "tenant_id", "role"),
    )


class Invitation(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Invitation to a tenant."""

    __tablename__ = "invitations"

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    invited_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    __table_args__ = (Index("ix_invitations_tenant_status", "tenant_id", "status"),)


class AuditEvent(Base):
    """Audit event (schema ``audit``). Written in the same transaction as the action."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_tenant_time", "tenant_id", "occurred_at"),
        Index("ix_audit_events_tenant_action", "tenant_id", "action"),
        {"schema": "audit"},
    )

    id: Mapped[UUID] = mapped_column(UUID7, primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
