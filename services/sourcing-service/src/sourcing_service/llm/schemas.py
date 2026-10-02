"""Pydantic schemas for validating LLM output (normalization)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_url: str | None = None
    source_type: str = "website"
    snippet: str | None = None


class _EmailItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    value: str
    type: str = "unknown"
    is_primary: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[_Evidence] = Field(default_factory=list)


class _PhoneItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    value: str
    type: str = "unknown"
    is_primary: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[_Evidence] = Field(default_factory=list)


class ContactItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str
    position: str | None = None
    role_category: str = "unknown"
    seniority: str = "unknown"
    emails: list[_EmailItem] = Field(default_factory=list)
    phones: list[_PhoneItem] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class NormalizedCandidate(BaseModel):
    """Result of normalizing one RawCandidate."""

    model_config = ConfigDict(extra="ignore")
    is_company: bool = True
    is_relevant: bool = True
    relevance_reason: str = ""
    company: dict[str, Any] = Field(default_factory=dict[str, Any])
    contacts: list[ContactItem] = Field(default_factory=list)
