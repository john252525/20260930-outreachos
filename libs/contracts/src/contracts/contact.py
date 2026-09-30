"""Contact contract v1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.base import EntityBase, Fact
from contracts.enums import (
    ConsentStatus,
    ContactStatus,
    EmailType,
    LawfulBasis,
    PhoneType,
    RoleCategory,
    Seniority,
)


class EmailAddress(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str
    type: EmailType = EmailType.UNKNOWN
    is_primary: bool = True
    is_verified: bool = False
    verified_at: datetime | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[dict[str, object]] = Field(default_factory=list)


class PhoneNumber(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str
    type: PhoneType = PhoneType.UNKNOWN
    is_primary: bool = True
    is_whatsapp: bool = False
    is_telegram: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[dict[str, object]] = Field(default_factory=list)


class MessengerHandle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel: str
    handle: str
    profile_url: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[dict[str, object]] = Field(default_factory=list)


class ContactSocialProfiles(BaseModel):
    model_config = ConfigDict(extra="ignore")

    linkedin: str | None = None
    telegram: str | None = None
    vk: str | None = None
    other: dict[str, str] = Field(default_factory=dict)


class ContactLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    country: Fact[str] = Field(default_factory=lambda: Fact[str]())
    city: Fact[str] = Field(default_factory=lambda: Fact[str]())
    timezone: str | None = None


class ContactMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    segment_id: UUID | None = None
    icp_version: int = 1
    role_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class Consent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email_opt_in: ConsentStatus = ConsentStatus.UNKNOWN
    email_opt_in_source: str | None = None
    email_opt_in_at: datetime | None = None
    messenger_opt_in: ConsentStatus = ConsentStatus.UNKNOWN
    gdpr_lawful_basis: LawfulBasis = LawfulBasis.UNKNOWN
    notes: str | None = None


class ContactOutreachHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_messages: int = 0
    last_contacted_at: datetime | None = None
    last_reply_at: datetime | None = None
    replied_positive: bool = False


class Contact(EntityBase):
    """Candidate person card."""

    company_id: UUID | None = None
    fingerprint: str
    status: ContactStatus = ContactStatus.CANDIDATE

    full_name: Fact[str] = Field(default_factory=lambda: Fact[str]())
    first_name: Fact[str] = Field(default_factory=lambda: Fact[str]())
    last_name: Fact[str] = Field(default_factory=lambda: Fact[str]())
    patronymic: Fact[str] = Field(default_factory=lambda: Fact[str]())

    position: Fact[str] = Field(default_factory=lambda: Fact[str]())
    role_category: RoleCategory = RoleCategory.UNKNOWN
    seniority: Seniority = Seniority.UNKNOWN

    emails: list[EmailAddress] = Field(default_factory=list)
    phones: list[PhoneNumber] = Field(default_factory=list)
    messengers: list[MessengerHandle] = Field(default_factory=list)
    social_profiles: ContactSocialProfiles = Field(default_factory=ContactSocialProfiles)
    location: ContactLocation = Field(default_factory=ContactLocation)
    language_preference: str | None = None

    match: ContactMatch = Field(default_factory=ContactMatch)
    consent: Consent = Field(default_factory=Consent)
    outreach_history: ContactOutreachHistory = Field(default_factory=ContactOutreachHistory)

    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
