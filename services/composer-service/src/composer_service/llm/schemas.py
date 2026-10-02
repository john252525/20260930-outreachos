"""Pydantic schemas for validating LLM output."""

from pydantic import BaseModel, ConfigDict, Field


class GeneratedEmail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str = ""
    body: str = ""


class FactualClaimExtract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claim: str
    evidence_url: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    is_hypothesis: bool = False
