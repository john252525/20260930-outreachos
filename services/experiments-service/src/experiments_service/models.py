"""ORM models for experiments-service."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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


class Experiment(
    Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SchemaVersionMixin, MetadataMixin
):
    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)

    segment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="email")
    icp_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    variable_type: Mapped[str] = mapped_column(String(32), nullable=False)
    variable_description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    variants: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    sample_size_target: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    sample_size_per_variant: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    minimum_detectable_effect: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    allocation_strategy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="fixed"
    )  # fixed | thompson

    decision: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_experiments_tenant_name"),
        Index("ix_experiments_tenant_status", "tenant_id", "status"),
    )
