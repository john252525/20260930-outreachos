"""Feature extraction for scoring."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SegmentFeatures:
    industries: list[str] = field(default_factory=list)
    sub_industries: list[str] = field(default_factory=list)
    company_sizes: list[str] = field(default_factory=list)
    employee_count_min: int | None = None
    employee_count_max: int | None = None
    geos: list[str] = field(default_factory=list)
    company_types: list[str] = field(default_factory=list)
    uses_technologies: list[str] = field(default_factory=list)
    does_not_use_technologies: list[str] = field(default_factory=list)
    pain_keywords: list[str] = field(default_factory=list)
    trigger_keywords: list[str] = field(default_factory=list)
    target_roles: list[str] = field(default_factory=list)


@dataclass
class CompanyFeatures:
    industry: str | None = None
    sub_industry: str | None = None
    employee_count: int | None = None
    employee_range: str = "unknown"
    country: str | None = None
    company_type: str | None = None
    tech_stack: list[str] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)
    text_blob: str = ""


@dataclass
class ContactFeatures:
    roles: list[str] = field(default_factory=list)
    role_categories: list[str] = field(default_factory=list)
    seniority_levels: list[str] = field(default_factory=list)


def extract_segment_features(segment: dict[str, Any]) -> SegmentFeatures:
    firm = segment.get("firmographic", {}) or {}
    tech = segment.get("technographic", {}) or {}
    pains = segment.get("pain_hypotheses", []) or []
    triggers = segment.get("trigger_events", []) or []
    roles = segment.get("roles_to_contact", []) or []
    return SegmentFeatures(
        industries=[i.lower() for i in (firm.get("industries") or [])],
        sub_industries=[i.lower() for i in (firm.get("sub_industries") or [])],
        company_sizes=[s.lower() for s in (firm.get("company_sizes") or [])],
        employee_count_min=firm.get("employee_count_min"),
        employee_count_max=firm.get("employee_count_max"),
        geos=[g.upper() for g in (firm.get("geos") or [])],
        company_types=[t.lower() for t in (firm.get("company_types") or [])],
        uses_technologies=[t.lower() for t in (tech.get("uses_technologies") or [])],
        does_not_use_technologies=[
            t.lower() for t in (tech.get("does_not_use_technologies") or [])
        ],
        pain_keywords=[(p.get("pain") or "").lower() for p in pains if p.get("pain")],
        trigger_keywords=[(t.get("trigger") or "").lower() for t in triggers if t.get("trigger")],
        target_roles=[(r.get("role_title") or "").lower() for r in roles if r.get("role_title")],
    )


def extract_company_features(company: dict[str, Any]) -> CompanyFeatures:
    def _val(f: str) -> str | None:
        v = company.get(f)
        if isinstance(v, dict):
            return v.get("value")
        return v

    size = company.get("size_estimate") or {}
    emp_count = size.get("employee_count")
    if isinstance(emp_count, dict):
        emp_count = emp_count.get("value")

    locations = company.get("locations") or []
    country = None
    for loc in locations:
        c = loc.get("country")
        if isinstance(c, dict):
            c = c.get("value")
        if c:
            country = c
            break

    tech = company.get("tech_stack") or []
    tech_values = [
        t.get("value", "").lower() for t in tech if isinstance(t, dict) and t.get("value")
    ]
    signals = company.get("signals") or []
    text_parts = [
        str(_val("name") or ""),
        str(_val("industry") or ""),
        str(_val("sub_industry") or ""),
        " ".join(str(s.get("summary", "")) for s in signals),
    ]
    text_blob = " ".join(text_parts).lower()
    return CompanyFeatures(
        industry=(_val("industry") or "").lower() or None,
        sub_industry=(_val("sub_industry") or "").lower() or None,
        employee_count=emp_count,
        employee_range=(size.get("employee_range") or "unknown").lower(),
        country=country,
        company_type=None,
        tech_stack=tech_values,
        signals=signals,
        text_blob=text_blob,
    )


def extract_contact_features(contacts: list[dict[str, Any]]) -> ContactFeatures:
    roles: list[str] = []
    categories: list[str] = []
    seniorities: list[str] = []
    for c in contacts:
        pos = c.get("position")
        if isinstance(pos, dict):
            pos = pos.get("value")
        if pos:
            roles.append(pos.lower())
        if c.get("role_category"):
            categories.append(c["role_category"])
        if c.get("seniority"):
            seniorities.append(c["seniority"])
    return ContactFeatures(roles=roles, role_categories=categories, seniority_levels=seniorities)
