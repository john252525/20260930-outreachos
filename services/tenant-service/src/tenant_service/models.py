"""ORM models for tenant-service."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import (
    MetadataMixin,
    SchemaVersionMixin,
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
