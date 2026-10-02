"""Deterministic scoring of a company+contacts against an ICP segment."""

from typing import Any

from sourcing_service.scoring.features import (
    CompanyFeatures,
    ContactFeatures,
    SegmentFeatures,
    extract_company_features,
    extract_contact_features,
    extract_segment_features,
)


class Scorer:
    """Scores a company+contacts by ICP segment weights."""

    def __init__(self, *, min_threshold: float = 0.5) -> None:
        self._min = min_threshold

    def score(
        self,
        *,
        normalized_company: dict[str, Any],
        contacts: list[dict[str, Any]],
        segment: dict[str, Any],
    ) -> tuple[float, dict[str, float], list[str]]:
        seg = extract_segment_features(segment)
        comp = extract_company_features(normalized_company)
        cont = extract_contact_features(contacts)
        weights = segment.get("scoring_weights") or {}
        reasons: list[str] = []
        breakdown: dict[str, float] = {}
        breakdown["industry_match"] = self._industry_match(seg, comp, reasons)
        breakdown["size_match"] = self._size_match(seg, comp, reasons)
        breakdown["geo_match"] = self._geo_match(seg, comp, reasons)
        breakdown["pain_match"] = self._pain_match(seg, comp, reasons)
        breakdown["trigger_match"] = self._trigger_match(seg, comp, reasons)
        breakdown["role_match"] = self._role_match(seg, cont, reasons)
        total = 0.0
        for key, val in breakdown.items():
            total += float(weights.get(key, 0.0)) * val
        total = round(min(max(total, 0.0), 1.0), 4)
        return total, breakdown, reasons

    def _industry_match(
        self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]
    ) -> float:
        if not seg.industries:
            return 0.5
        if not comp.industry:
            return 0.0
        if comp.industry in seg.industries:
            reasons.append(f"industry exact: {comp.industry}")
            return 1.0
        for ind in seg.industries:
            if ind in comp.industry or comp.industry in ind:
                reasons.append(f"industry partial: {comp.industry} ~ {ind}")
                return 0.7
        if comp.sub_industry and comp.sub_industry in seg.sub_industries:
            reasons.append(f"sub_industry match: {comp.sub_industry}")
            return 0.8
        return 0.0

    def _size_match(self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]) -> float:
        if not seg.company_sizes and seg.employee_count_min is None:
            return 0.5
        if comp.employee_count is not None:
            if seg.employee_count_min is not None and comp.employee_count < seg.employee_count_min:
                return 0.0
            if seg.employee_count_max is not None and comp.employee_count > seg.employee_count_max:
                return 0.0
            reasons.append(f"employee_count in range: {comp.employee_count}")
            return 1.0
        if comp.employee_range != "unknown" and comp.employee_range in seg.company_sizes:
            reasons.append(f"size range match: {comp.employee_range}")
            return 1.0
        return 0.0

    def _geo_match(self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]) -> float:
        if not seg.geos:
            return 0.5
        if not comp.country:
            return 0.3
        if comp.country.upper() in seg.geos:
            reasons.append(f"geo match: {comp.country}")
            return 1.0
        return 0.0

    def _pain_match(self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]) -> float:
        if not seg.pain_keywords:
            return 0.5
        blob = comp.text_blob
        hits = sum(1 for kw in seg.pain_keywords if kw and kw in blob)
        if hits == 0:
            return 0.0
        score = min(hits / len(seg.pain_keywords), 1.0)
        reasons.append(f"pain keywords matched: {hits}/{len(seg.pain_keywords)}")
        return round(score, 4)

    def _trigger_match(
        self, seg: SegmentFeatures, comp: CompanyFeatures, reasons: list[str]
    ) -> float:
        if not seg.trigger_keywords:
            return 0.5
        if not comp.signals:
            return 0.0
        signal_text = " ".join(str(s.get("summary", "")) for s in comp.signals).lower()
        hits = sum(1 for kw in seg.trigger_keywords if kw and kw in signal_text)
        if hits == 0:
            return 0.0
        score = min(hits / len(seg.trigger_keywords), 1.0)
        reasons.append(f"triggers matched: {hits}")
        return round(score, 4)

    def _role_match(self, seg: SegmentFeatures, cont: ContactFeatures, reasons: list[str]) -> float:
        if not seg.target_roles:
            return 0.5
        if not cont.roles:
            return 0.0
        for role in cont.roles:
            for target in seg.target_roles:
                if target in role or role in target:
                    reasons.append(f"role match: {role}")
                    return 1.0
        if "decision_maker" in cont.role_categories:
            return 0.7
        if "champion" in cont.role_categories or "influencer" in cont.role_categories:
            return 0.5
        return 0.2
