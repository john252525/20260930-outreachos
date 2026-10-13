"""API schemas for ml-scoring."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: UUID


class ScoreResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contact_id: UUID
    score: float
    components: dict[str, float]
    model_version: str


class FeaturesUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_id: UUID
    role_category: str | None = None
    seniority: str | None = None
    company_industry: str | None = None
    company_size_range: str | None = None
    company_country: str | None = None
    company_employee_count: int | None = None
    company_signals_count: int = 0
    days_since_company_created: int | None = None
    has_reply: bool = False
    has_positive_reply: bool = False
    messages_sent: int = 0
    last_message_sent_at: datetime | None = None


class FeaturesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: UUID
    contact_id: UUID
    role_category: str | None
    seniority: str | None
    company_industry: str | None
    company_employee_count: int | None
    company_signals_count: int
    has_reply: bool
    has_positive_reply: bool
    messages_sent: int
    updated_at: datetime
