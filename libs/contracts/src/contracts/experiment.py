"""Experiment contract v1 — A/B hypothesis for outreach."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.base import EntityBase
from contracts.enums import (
    Channel,
    ExperimentStatus,
    ExperimentVariableType,
    PrimaryMetric,
)


class ExperimentScope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    segment_id: UUID | None = None
    channel: Channel = Channel.EMAIL
    icp_version: int = 1


class ExperimentVariable(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: ExperimentVariableType = ExperimentVariableType.BODY
    description: str = ""


class Variant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    description: str = ""
    template_id: str = ""
    weight: float = Field(default=0.5, ge=0.0, le=1.0)


class ExperimentMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary: PrimaryMetric = PrimaryMetric.REPLY_RATE
    secondary: list[str] = Field(default_factory=list)


class VariantResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    variant_id: str
    sent: int = 0
    replied: int = 0
    positive_replied: int = 0
    meetings_booked: int = 0
    primary_metric_value: float = 0.0
    confidence_interval: list[float] = Field(default_factory=list)


class ExperimentResults(BaseModel):
    model_config = ConfigDict(extra="ignore")

    variants: list[VariantResult] = Field(default_factory=list)
    winner_variant_id: str | None = None
    is_significant: bool = False
    concluded_at: datetime | None = None


class Experiment(EntityBase):
    """A/B experiment."""

    name: str
    hypothesis: str = ""
    status: ExperimentStatus = ExperimentStatus.DRAFT

    scope: ExperimentScope = Field(default_factory=ExperimentScope)
    variable: ExperimentVariable = Field(default_factory=ExperimentVariable)
    variants: list[Variant] = Field(default_factory=list)
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)

    sample_size_target: int = 200
    sample_size_per_variant: int = 100
    confidence_level: float = 0.95
    minimum_detectable_effect: float = 0.05

    results: ExperimentResults = Field(default_factory=ExperimentResults)
    decision: str | None = None

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> Experiment:
        if not self.variants:
            return self
        total = sum(v.weight for v in self.variants)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"variant weights must sum to 1.0, got {total}")
        return self
