"""API schemas for experiments-service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VariantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str = ""
    description: str = ""
    template_id: str = ""
    weight: float = Field(default=0.5, ge=0.0, le=1.0)


class MetricsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: str = "positive_reply_rate"
    secondary: list[str] = Field(default_factory=list)


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    hypothesis: str = ""
    variable_type: str
    variable_description: str = ""
    channel: str = "email"
    segment_id: str | None = None
    icp_version: int | None = None
    variants: list[VariantIn] = Field(min_length=1)
    metrics: MetricsIn = Field(default_factory=MetricsIn)
    sample_size_target: int = 200
    sample_size_per_variant: int = 100
    confidence_level: float = 0.95
    minimum_detectable_effect: float = 0.05
    allocation_strategy: str = Field(default="fixed", pattern="^(fixed|thompson)$")


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)
    id: UUID
    tenant_id: UUID
    name: str
    hypothesis: str
    status: str
    channel: str
    segment_id: str | None
    icp_version: int | None
    variable_type: str
    variable_description: str
    variants: list[dict[str, Any]]
    metrics: dict[str, Any]
    sample_size_target: int
    sample_size_per_variant: int
    confidence_level: float
    minimum_detectable_effect: float
    allocation_strategy: str = "fixed"
    results: dict[str, Any]
    decision: str | None
    started_at: datetime | None
    finished_at: datetime | None
    schema_version: str
    created_at: datetime
    updated_at: datetime


class ExperimentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    name: str
    status: str
    channel: str
    variants: list[dict[str, Any]]
    created_at: datetime


class AssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: UUID


class AssignResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    experiment_id: UUID
    contact_id: UUID
    variant_id: str | None = None
    template_id: str | None = None
