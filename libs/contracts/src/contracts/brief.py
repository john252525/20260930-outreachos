"""Brief contract v1 — structured project intake."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.base import EntityBase, utc_now
from contracts.enums import BriefStatus, PrimaryGoal, ToneOfVoice


class Attachment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    storage_url: str


class RawInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str | None = None
    urls: list[str] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    transcript: str | None = None
    submitted_at: datetime = Field(default_factory=utc_now)


class QAItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str
    answer: str | None = None
    asked_at: datetime = Field(default_factory=utc_now)
    answered_at: datetime | None = None
    generated_by: str = "llm"
    question_template_id: str | None = None


class BriefIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_name: str
    company_name: str | None = None
    company_url: str | None = None
    one_liner: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    language: str = "ru"
    geo_primary: list[str] = Field(default_factory=list)
    geo_secondary: list[str] = Field(default_factory=list)


class PriceRange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    min: float | None = None
    max: float | None = None
    currency: str | None = None
    model: str = "unknown"


class BriefOffering(BaseModel):
    model_config = ConfigDict(extra="ignore")

    what_we_sell: str = ""
    categories: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    price_range: PriceRange = Field(default_factory=PriceRange)
    sales_cycle_days_estimate: int | None = None


class BriefTargetingHints(BaseModel):
    model_config = ConfigDict(extra="ignore")

    known_competitors: list[str] = Field(default_factory=list)
    known_customers_examples: list[str] = Field(default_factory=list)
    must_have_criteria: list[str] = Field(default_factory=list)
    must_not_have_criteria: list[str] = Field(default_factory=list)
    geography_notes: str | None = None
    company_size_hint: str | None = None
    role_hints: list[str] = Field(default_factory=list)


class BriefOutreachGoals(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary_goal: PrimaryGoal = PrimaryGoal.LEAD_GEN
    goal_description: str | None = None
    target_meetings_per_month: int | None = None
    tone_of_voice: ToneOfVoice = ToneOfVoice.NEUTRAL
    forbidden_topics: list[str] = Field(default_factory=list)
    required_mentions: list[str] = Field(default_factory=list)


class MissingInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str
    why_needed: str
    priority: str = "medium"


class Brief(EntityBase):
    """Structured project brief."""

    status: BriefStatus = BriefStatus.DRAFT
    raw_input: RawInput = Field(default_factory=RawInput)
    qa_history: list[QAItem] = Field(default_factory=list)
    identity: BriefIdentity
    offering: BriefOffering = Field(default_factory=BriefOffering)
    targeting_hints: BriefTargetingHints = Field(default_factory=BriefTargetingHints)
    outreach_goals: BriefOutreachGoals = Field(default_factory=BriefOutreachGoals)
    missing_info: list[MissingInfo] = Field(default_factory=list)
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
