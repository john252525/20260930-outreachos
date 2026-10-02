"""Deterministic fact checker for generated messages."""

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

_NUMBER_RE = re.compile(r"\b\d+[\s]?(?:%|руб|тыс|млн|млрд|лет|год|года|месяц|месяцев)")


@dataclass
class FactualClaim:
    claim: str
    evidence_url: str | None
    confidence: float
    is_hypothesis: bool
    source_field: str | None


@dataclass
class FactCheckResult:
    claims: list[FactualClaim] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)


class FactChecker:
    """Checks factual claims in a message (deterministic, no LLM)."""

    def __init__(self, *, strict: bool = True, min_confidence: float = 0.6) -> None:
        self._strict = strict
        self._min_confidence = min_confidence

    def check(
        self,
        *,
        body: str,
        subject: str | None,
        contact: dict[str, Any],
        company: dict[str, Any] | None,
    ) -> FactCheckResult:
        result = FactCheckResult()
        text = f"{subject or ''}\n{body}"

        contact_name = self._fact_value(contact.get("full_name"))
        if contact_name:
            for part in contact_name.split():
                if len(part) > 2 and part in text:
                    result.claims.append(
                        FactualClaim(
                            claim=part,
                            evidence_url=None,
                            confidence=1.0,
                            is_hypothesis=False,
                            source_field="contact.full_name",
                        )
                    )
                    break

        company_name = self._fact_value(company.get("name")) if company else None
        if company_name:
            words = [w for w in re.findall(r"\w+", company_name) if len(w) > 2]
            for w in words:
                if w in text:
                    result.claims.append(
                        FactualClaim(
                            claim=w,
                            evidence_url=None,
                            confidence=1.0,
                            is_hypothesis=False,
                            source_field="company.name",
                        )
                    )
                    break

        position = self._fact_value(contact.get("position"))
        if position and position.lower() in text.lower():
            result.claims.append(
                FactualClaim(
                    claim=position,
                    evidence_url=None,
                    confidence=0.9,
                    is_hypothesis=False,
                    source_field="contact.position",
                )
            )

        if company:
            for signal in company.get("signals", []) or []:
                summary = signal.get("summary", "")
                if not summary:
                    continue
                signal_words = [w for w in re.findall(r"\w+", summary) if len(w) > 4]
                hits = sum(1 for w in signal_words if w.lower() in text.lower())
                if hits >= 1:
                    result.claims.append(
                        FactualClaim(
                            claim=summary[:200],
                            evidence_url=signal.get("source_url"),
                            confidence=0.8,
                            is_hypothesis=False,
                            source_field="company.signals",
                        )
                    )

        seen_numbers: set[str] = set()
        for m in _NUMBER_RE.finditer(text):
            num_str = m.group(0)
            if num_str in seen_numbers:
                continue
            seen_numbers.add(num_str)
            found = False
            for s in (company or {}).get("signals", []) or []:
                if num_str in (s.get("summary") or ""):
                    found = True
                    break
            if not found:
                result.claims.append(
                    FactualClaim(
                        claim=num_str,
                        evidence_url=None,
                        confidence=0.3,
                        is_hypothesis=True,
                        source_field=None,
                    )
                )
                result.warnings.append(f"unverified_number:{num_str}")

        if self._strict:
            hypotheses = [c for c in result.claims if c.is_hypothesis]
            if hypotheses:
                result.warnings.append(f"hypotheses_present:{len(hypotheses)}")

        return result

    @staticmethod
    def _fact_value(fact: Any) -> str | None:
        if fact is None:
            return None
        if isinstance(fact, str):
            return fact
        if isinstance(fact, dict):
            return fact.get("value")
        return None
