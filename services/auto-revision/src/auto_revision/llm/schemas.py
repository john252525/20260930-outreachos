"""Pydantic schemas for validating LLM output (auto-revision)."""

from pydantic import BaseModel, ConfigDict, Field


class ProposedChange(BaseModel):
    model_config = ConfigDict(extra="ignore")
    variable_type: str = Field(default="body", pattern="^(subject|body|cta|tone|offer|other)$")
    description: str = ""
    example_before: str = ""
    example_after: str = ""


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    diagnosis: str = ""
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    llm_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RevisedTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    system_prompt: str = ""
    user_prompt_template: str = ""
    variables_used: list[str] = Field(default_factory=list)
    summary: str = ""
