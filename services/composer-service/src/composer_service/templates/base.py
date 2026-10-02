"""Template abstraction for message generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemplateContext:
    """Context for generation. Filled by ComposerService."""

    contact: dict[str, Any]
    company: dict[str, Any] | None
    sender: dict[str, Any]
    brief: dict[str, Any]
    icp: dict[str, Any]
    segment: dict[str, Any]
    channel: str
    language: str = "ru"
    extra: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class RenderedTemplate:
    """Result of rendering a template — fed to the LLM as a basis."""

    system_prompt: str
    user_prompt: str
    subject_hint: str | None
    required_mentions: list[str]
    forbidden_phrases: list[str]
    variables_used: dict[str, Any]


class Template(ABC):
    """Base template interface."""

    template_id: str
    template_version: str
    channel: str

    @abstractmethod
    def render(self, context: TemplateContext) -> RenderedTemplate:
        """Turn the context into a prompt."""

    def validate_output(self, *, subject: str | None, body: str) -> list[str]:
        """Check the result after the LLM. Returns warnings (not errors)."""
        return []

    @staticmethod
    def fact_value(fact: Any) -> str | None:
        if fact is None:
            return None
        if isinstance(fact, str):
            return fact
        if isinstance(fact, dict):
            v = fact.get("value")
            return str(v) if v is not None else None
        return None

    @staticmethod
    def primary_email(contact: dict[str, Any]) -> str | None:
        for e in contact.get("emails", []) or []:
            if e.get("is_primary"):
                v = e.get("value")
                return str(v) if v is not None else None
        return None

    @staticmethod
    def size_value(company: dict[str, Any]) -> str | None:
        size = company.get("size_estimate") or {}
        er = size.get("employee_range")
        if er and er != "unknown":
            return str(er)
        ec = size.get("employee_count")
        if isinstance(ec, dict):
            ec = ec.get("value")
        if ec:
            return f"{ec} сотрудников"
        return None

    @staticmethod
    def location_value(company: dict[str, Any]) -> str | None:
        for loc in company.get("locations", []) or []:
            if loc.get("is_hq"):
                city = loc.get("city")
                country = loc.get("country")
                city_v = city.get("value") if isinstance(city, dict) else city
                country_v = country.get("value") if isinstance(country, dict) else country
                if city_v:
                    return f"{city_v}, {country_v}" if country_v else str(city_v)
                if country_v:
                    return str(country_v)
        return None
