"""ORM models for icp-service."""

from typing import Any

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


class ICP(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "icps"

    # brief_id has no FK: briefs live in a different service
    brief_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    segments_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
