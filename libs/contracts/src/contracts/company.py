"""Company contract v1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.base import EntityBase, Fact, utc_now
from contracts.enums import CompanySize, CompanyStatus, SignalType


class SizeEstimate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    employee_count: Fact[int] = Field(default_factory=lambda: Fact[int]())
    employee_range: CompanySize = CompanySize.UNKNOWN
    revenue_estimate: Fact[float] = Field(default_factory=lambda: Fact[float]())
    revenue_currency: str | None = None


class Location(BaseModel):
    model_config = ConfigDict(extra="ignore")

    country: Fact[str] = Field(default_factory=lambda: Fact[str]())
    city: Fact[str] = Field(default_factory=lambda: Fact[str]())
    address: Fact[str] = Field(default_factory=lambda: Fact[str]())
    is_hq: bool = True


class RegistryIds(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ru_inn: str | None = None
    ru_ogrn: str | None = None
    other: dict[str, str] = Field(default_factory=dict)


class SocialProfiles(BaseModel):
    model_config = ConfigDict(extra="ignore")

    linkedin: str | None = None
    telegram: str | None = None
    vk: str | None = None
    other: dict[str, str] = Field(default_factory=dict)


class Signal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: SignalType = SignalType.OTHER
    summary: str
    detected_at: datetime = Field(default_factory=utc_now)
    source_url: str | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore")

    industry_match: float = 0.0
    size_match: float = 0.0
    geo_match: float = 0.0
    pain_match: float = 0.0
    trigger_match: float = 0.0
    role_match: float = 0.0


class CompanyMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    segment_id: UUID | None = None
    icp_version: int = 1
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    matched_criteria: list[str] = Field(default_factory=list)
    failed_criteria: list[str] = Field(default_factory=list)
    reason: str = ""


class OutreachHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_contacts: int = 0
    total_messages: int = 0
    last_contacted_at: datetime | None = None


class Company(EntityBase):
    """Candidate company card."""

    fingerprint: str
    status: CompanyStatus = CompanyStatus.CANDIDATE

    name: Fact[str] = Field(default_factory=lambda: Fact[str]())
    legal_name: Fact[str] = Field(default_factory=lambda: Fact[str]())
    domain: Fact[str] = Field(default_factory=lambda: Fact[str]())
    website: Fact[str] = Field(default_factory=lambda: Fact[str]())
    industry: Fact[str] = Field(default_factory=lambda: Fact[str]())
    sub_industry: Fact[str] = Field(default_factory=lambda: Fact[str]())

    size_estimate: SizeEstimate = Field(default_factory=SizeEstimate)
    locations: list[Location] = Field(default_factory=list)
    registry_ids: RegistryIds = Field(default_factory=RegistryIds)
    social_profiles: SocialProfiles = Field(default_factory=SocialProfiles)

    tech_stack: list[Fact[str]] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)

    match: CompanyMatch = Field(default_factory=CompanyMatch)
    contacts_count: int = 0
    outreach_history: OutreachHistory = Field(default_factory=OutreachHistory)

    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
