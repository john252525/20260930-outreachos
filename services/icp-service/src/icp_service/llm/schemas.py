"""Pydantic schemas for validating LLM output (not contracts, not API)."""

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticUndefined


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        return type(None) in get_args(annotation)
    return False


def _default_for(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return _default_for(non_none[0])
        return None
    if annotation is str:
        return ""
    if annotation in (int, float):
        return 0
    if annotation is bool:
        return False
    if origin in (list, tuple, set):
        return []
    if origin is dict:
        return {}
    return None


class LLMSchemaBase(BaseModel):
    """Tolerant base: coerces null for str/list fields, fills missing."""

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
                    continue
                else:
                    fixed[name] = _default_for(field.annotation)
            else:
                fixed[name] = value
        for key, val in data.items():
            if key not in cls.model_fields:
                fixed[key] = val
        return fixed


class _AntiICP(LLMSchemaBase):
    description: str = ""
    exclude_industries: list[str] = Field(default_factory=list)
    exclude_company_sizes: list[str] = Field(default_factory=list)
    exclude_geos: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class _Firmographic(LLMSchemaBase):
    industries: list[str] = Field(default_factory=list)
    sub_industries: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    revenue_range: dict[str, Any] | None = None
    geos: list[str] = Field(default_factory=list)
    company_types: list[str] = Field(default_factory=list)


class _Technographic(LLMSchemaBase):
    uses_technologies: list[str] = Field(default_factory=list)
    does_not_use_technologies: list[str] = Field(default_factory=list)


class _PainHypothesis(LLMSchemaBase):
    pain: str
    why_relevant: str = ""
    how_we_solve: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class _TriggerEvent(LLMSchemaBase):
    trigger: str
    detection_hint: str = ""
    weight: float = Field(default=0.5, ge=0.0, le=1.0)


class _RoleToContact(LLMSchemaBase):
    role_title: str
    role_category: str = "unknown"
    priority: str = "medium"
    why: str = ""


class _ScoringWeights(LLMSchemaBase):
    industry_match: float = 0.0
    size_match: float = 0.0
    geo_match: float = 0.0
    pain_match: float = 0.0
    trigger_match: float = 0.0
    role_match: float = 0.0


class _Segment(LLMSchemaBase):
    name: str
    description: str = ""
    priority: str = "medium"
    estimated_size: int | None = None
    firmographic: _Firmographic = Field(default_factory=_Firmographic)
    technographic: _Technographic = Field(default_factory=_Technographic)
    pain_hypotheses: list[_PainHypothesis] = Field(default_factory=list)
    trigger_events: list[_TriggerEvent] = Field(default_factory=list)
    roles_to_contact: list[_RoleToContact] = Field(default_factory=list)
    scoring_weights: _ScoringWeights = Field(default_factory=_ScoringWeights)
    estimated_reply_rate: float | None = None
    notes: str | None = None


class ICPGenerated(LLMSchemaBase):
    anti_icp: _AntiICP = Field(default_factory=_AntiICP)
    segments: list[_Segment] = Field(default_factory=list)
    llm_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
