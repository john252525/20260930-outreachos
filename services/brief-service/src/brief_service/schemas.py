"""API schemas for brief-service (distinct from contracts and LLM schemas)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RawInputSubmit(BaseModel):
    """Initial project input."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=100_000)
    urls: list[HttpUrl] = Field(default_factory=list, max_length=10)
    transcript: str | None = Field(default=None, max_length=200_000)


class AnswerSubmit(BaseModel):
    """Answer to a clarifying question."""

    model_config = ConfigDict(extra="forbid")

    question_index: int = Field(ge=0)
    answer: str = Field(min_length=1, max_length=10_000)


class AbandonSubmit(BaseModel):
    """Reason for abandoning a brief."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=2000)


class ResetQuestionSubmit(BaseModel):
    """Which question to reset."""

    model_config = ConfigDict(extra="forbid")

    question_index: int = Field(ge=0)


class BriefRead(BaseModel):
    """Full Brief for reading."""

    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: UUID
    tenant_id: UUID
    status: str
    completeness_score: float
    raw_input: dict[str, Any] = Field(default_factory=dict[str, Any])
    qa_history: list[dict[str, Any]] = Field(default_factory=list)
    identity: dict[str, Any] = Field(default_factory=dict[str, Any])
    offering: dict[str, Any] = Field(default_factory=dict[str, Any])
    targeting_hints: dict[str, Any] = Field(default_factory=dict[str, Any])
    outreach_goals: dict[str, Any] = Field(default_factory=dict[str, Any])
    missing_info: list[dict[str, Any]] = Field(default_factory=list)
    schema_version: str
    metadata: dict[str, Any] = Field(default_factory=dict[str, Any], validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime
    created_by: str


class BriefSummary(BaseModel):
    """Short version for lists."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    status: str
    completeness_score: float
    project_name: str | None = None
    created_at: datetime
    updated_at: datetime
