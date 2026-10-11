"""Pydantic schemas for validating LLM output (classification)."""

from pydantic import BaseModel, ConfigDict, Field


class LLMClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = Field(
        ...,
        pattern=(
            "^(positive|negative|not_interested|wrong_person|auto_reply|"
            "question|unsubscribe|out_of_office|unknown)$"
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0)
    sentiment: str = Field(..., pattern="^(positive|neutral|negative)$")
    intent: str | None = None
    extracted_questions: list[str] = Field(default_factory=list)
    extracted_actions: list[str] = Field(default_factory=list)
    suggested_action: str = Field(
        ...,
        pattern="^(reply|schedule_meeting|forward_to_human|add_to_nurture|unsubscribe|close)$",
    )
    suggested_action_reason: str = ""
    language: str | None = None
    reasoning: str = ""
