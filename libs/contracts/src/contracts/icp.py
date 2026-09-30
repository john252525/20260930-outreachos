"""ICP contract v1 — ideal customer profile with segments."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.base import EntityBase
from contracts.enums import CompanySize, CompanyType, Priority, RoleCategory


class AntiICP(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = ""
    exclude_industries: list[str] = Field(default_factory=list)
    exclude_company_sizes: list[CompanySize] = Field(default_factory=list)
    exclude_geos: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class RevenueRange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    min: float | None = None
    max: float | None = None
    currency: str | None = None


class Firmographic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    industries: list[str] = Field(default_factory=list)
    sub_industries: list[str] = Field(default_factory=list)
    company_sizes: list[CompanySize] = Field(default_factory=list)
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    revenue_range: RevenueRange = Field(default_factory=RevenueRange)
    geos: list[str] = Field(default_factory=list)
    company_types: list[CompanyType] = Field(default_factory=list)


class Technographic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uses_technologies: list[str] = Field(default_factory=list)
    does_not_use_technologies: list[str] = Field(default_factory=list)


class PainHypothesis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pain: str
    why_relevant: str = ""
    how_we_solve: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TriggerEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trigger: str
    detection_hint: str = ""
    weight: float = Field(default=0.0, ge=0.0, le=1.0)


class RoleToContact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role_title: str
    role_category: RoleCategory = RoleCategory.UNKNOWN
    priority: Priority = Priority.MEDIUM
    why: str = ""


class ScoringWeights(BaseModel):
    model_config = ConfigDict(extra="ignore")

    industry_match: float = 0.25
    size_match: float = 0.15
    geo_match: float = 0.10
    pain_match: float = 0.20
    trigger_match: float = 0.20
    role_match: float = 0.10

    @model_validator(mode="after")
    def _sum_to_one(self) -> ScoringWeights:
        total = (
            self.industry_match
            + self.size_match
            + self.geo_match
            + self.pain_match
            + self.trigger_match
            + self.role_match
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scoring weights must sum to 1.0, got {total}")
        return self


class Segment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    estimated_size: int | None = None
    firmographic: Firmographic = Field(default_factory=Firmographic)
    technographic: Technographic = Field(default_factory=Technographic)
    pain_hypotheses: list[PainHypothesis] = Field(default_factory=list)
    trigger_events: list[TriggerEvent] = Field(default_factory=list)
    roles_to_contact: list[RoleToContact] = Field(default_factory=list)
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    estimated_reply_rate: float | None = None
    notes: str | None = None


class ICP(EntityBase):
    """Ideal customer profile."""

    brief_id: UUID
    version: int = 1
    anti_icp: AntiICP = Field(default_factory=AntiICP)
    segments: list[Segment] = Field(default_factory=list)
    generated_by: str = "llm"
    llm_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
