"""Pydantic schemas used to validate LLM output (not contracts, not API schemas).

LLMs are quirky: they often send ``null`` where a string or list is expected,
or omit fields. ``LLMSchemaBase`` normalizes those quirks before validation so
a single bad field does not blow up the whole pipeline.
"""

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticUndefined


def _default_for(annotation: Any) -> Any:
    """Best-effort default for a field annotation when the LLM sent null."""
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):  # Optional[...] / X | None
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return _default_for(non_none[0])
        return None
    if annotation in (str,):
        return ""
    if annotation in (int, float):
        return 0
    if annotation is bool:
        return False
    if origin in (list, tuple, set):
        return []
    if origin is dict:
        return {}
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {}
    return None


class LLMSchemaBase(BaseModel):
    """Base schema tolerant to common LLM output quirks (null for str/list)."""

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        fixed: dict[str, Any] = {}
        for name, field in cls.model_fields.items():
            if name not in data:
                continue
            value = data[name]
            if value is None and not _is_optional(field.annotation):
                if field.default is not PydanticUndefined and field.default is not None:
                    fixed[name] = field.default
                elif field.default_factory is not None:
                    # let pydantic apply the factory
                    continue
                else:
                    fixed[name] = _default_for(field.annotation)
            else:
                fixed[name] = value
        # preserve unknown keys (ignored later, but nested models may use them)
        for key, val in data.items():
            if key not in cls.model_fields:
                fixed[key] = val
        return fixed


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        return type(None) in get_args(annotation)
    return False


class _PriceRange(LLMSchemaBase):
    min: float | None = None
    max: float | None = None
    currency: str | None = None
    model: str = "unknown"


class _Identity(LLMSchemaBase):
    project_name: str | None = None
    company_name: str | None = None
    company_url: str | None = None
    one_liner: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    language: str = "ru"
    geo_primary: list[str] = Field(default_factory=list)
    geo_secondary: list[str] = Field(default_factory=list)


class _Offering(LLMSchemaBase):
    what_we_sell: str = ""
    categories: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    price_range: _PriceRange = Field(default_factory=_PriceRange)
    sales_cycle_days_estimate: int | None = None


class _TargetingHints(LLMSchemaBase):
    known_competitors: list[str] = Field(default_factory=list)
    known_customers_examples: list[str] = Field(default_factory=list)
    must_have_criteria: list[str] = Field(default_factory=list)
    must_not_have_criteria: list[str] = Field(default_factory=list)
    geography_notes: str | None = None
    company_size_hint: str | None = None
    role_hints: list[str] = Field(default_factory=list)


class _OutreachGoals(LLMSchemaBase):
    primary_goal: str = "lead_gen"
    goal_description: str | None = None
    target_meetings_per_month: int | None = None
    tone_of_voice: str = "neutral"
    forbidden_topics: list[str] = Field(default_factory=list)
    required_mentions: list[str] = Field(default_factory=list)


class ExtractSchema(LLMSchemaBase):
    identity: _Identity = Field(default_factory=_Identity)
    offering: _Offering = Field(default_factory=_Offering)
    targeting_hints: _TargetingHints = Field(default_factory=_TargetingHints)
    outreach_goals: _OutreachGoals = Field(default_factory=_OutreachGoals)


class Question(LLMSchemaBase):
    question: str = ""
    why_needed: str = ""
    target_field: str = ""
    priority: str = "medium"


class QuestionsSchema(LLMSchemaBase):
    questions: list[Question] = Field(default_factory=list)
