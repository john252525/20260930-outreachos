"""Unit tests for the composite classifier."""

from typing import Any

import pytest
from reply_classifier.classifier.base import (
    ClassificationResult,
    NextAction,
    ReplyCategory,
    Sentiment,
)
from reply_classifier.classifier.composite import CompositeClassifier
from reply_classifier.classifier.rule_fallback import RuleBasedClassifier


class FakeLLM:
    """Fake LLMClassifier that records calls."""

    def __init__(self, result: ClassificationResult | None = None, boom: bool = False) -> None:
        self.calls = 0
        self._result = result
        self._boom = boom

    async def classify(self, **kwargs: Any) -> ClassificationResult:
        self.calls += 1
        if self._boom:
            raise RuntimeError("llm down")
        assert self._result is not None
        return self._result


def _llm_result() -> ClassificationResult:
    return ClassificationResult(
        category=ReplyCategory.QUESTION,
        confidence=0.9,
        sentiment=Sentiment.POSITIVE,
        suggested_action=NextAction.REPLY,
        classified_by="llm:test",
    )


@pytest.mark.asyncio
async def test_rule_takes_precedence() -> None:
    llm = FakeLLM(_llm_result())
    clf = CompositeClassifier(RuleBasedClassifier(), llm)  # type: ignore[arg-type]
    result = await clf.classify(
        tenant_id="t",
        original_message={},
        from_email="x@y.com",
        from_name=None,
        subject="Re: Offer",
        body="Please unsubscribe me.",
    )
    assert result.category == ReplyCategory.UNSUBSCRIBE
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_llm_used_when_rules_unsure() -> None:
    llm = FakeLLM(_llm_result())
    clf = CompositeClassifier(RuleBasedClassifier(), llm)  # type: ignore[arg-type]
    result = await clf.classify(
        tenant_id="t",
        original_message={},
        from_email="x@y.com",
        from_name=None,
        subject="Re: Offer",
        body="Хм, посмотрю позже.",
    )
    assert result.category == ReplyCategory.QUESTION
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_llm_failure_without_rule_returns_unknown() -> None:
    llm = FakeLLM(_llm_result(), boom=True)
    clf = CompositeClassifier(RuleBasedClassifier(), llm)  # type: ignore[arg-type]
    result = await clf.classify(
        tenant_id="t",
        original_message={},
        from_email="x@y.com",
        from_name=None,
        subject="Re: Offer",
        body="нечто неопределённое",
    )
    assert result.category == ReplyCategory.UNKNOWN
    assert result.classified_by == "fallback"


@pytest.mark.asyncio
async def test_llm_failure_with_low_rule_falls_back_to_rule() -> None:
    llm = FakeLLM(_llm_result(), boom=True)
    # raise min_confidence so positive-rule (0.7) doesn't short-circuit
    clf = CompositeClassifier(RuleBasedClassifier(), llm, min_confidence=0.9)  # type: ignore[arg-type]
    result = await clf.classify(
        tenant_id="t",
        original_message={},
        from_email="x@y.com",
        from_name=None,
        subject="Re: Offer",
        body="Интересно, расскажите подробнее.",
    )
    assert result.category in (ReplyCategory.POSITIVE, ReplyCategory.QUESTION)
