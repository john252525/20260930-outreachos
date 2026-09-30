"""Reusable ORM mixins."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.types import UUID7, generate_uuid7


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(UUID7, primary_key=True, default=generate_uuid7)


class TenantMixin:
    tenant_id: Mapped[UUID] = mapped_column(UUID7, nullable=False, index=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SchemaVersionMixin:
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")


class MetadataMixin:
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
