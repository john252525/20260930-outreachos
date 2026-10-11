"""Composite classifier: rules first, LLM as fallback."""

from typing import Any

import structlog

from reply_classifier.classifier.base import (
    ClassificationResult,
    NextAction,
    ReplyCategory,
    Sentiment,
)
from reply_classifier.classifier.llm_classifier import LLMClassifier
from reply_classifier.classifier.rule_fallback import RuleBasedClassifier

logger = structlog.get_logger()


class CompositeClassifier:
    """Try deterministic rules first, fall back to the LLM."""

    def __init__(
        self,
        rule: RuleBasedClassifier,
        llm: LLMClassifier,
        *,
        min_confidence: float = 0.6,
    ) -> None:
        self._rule = rule
        self._llm = llm
        self._min_confidence = min_confidence

    async def classify(
        self,
        *,
        tenant_id: str,
        original_message: dict[str, Any],
        from_email: str,
        from_name: str | None,
        subject: str | None,
        body: str,
        trace_id: str = "",
    ) -> ClassificationResult:
        rule_result = self._rule.classify(subject=subject, body=body, from_email=from_email)
        if rule_result is not None and rule_result.confidence >= self._min_confidence:
            logger.debug("reply_classified_by_rule", category=rule_result.category.value)
            return rule_result

        try:
            return await self._llm.classify(
                tenant_id=tenant_id,
                original_message=original_message,
                from_email=from_email,
                from_name=from_name,
                subject=subject,
                body=body,
                trace_id=trace_id,
            )
        except Exception as e:
            logger.exception("reply_llm_classify_failed", error=str(e))
            if rule_result is not None:
                return rule_result
            return ClassificationResult(
                category=ReplyCategory.UNKNOWN,
                confidence=0.0,
                sentiment=Sentiment.NEUTRAL,
                suggested_action=NextAction.FORWARD_TO_HUMAN,
                suggested_action_reason="Классификация не удалась — требуется ручной разбор",
                classified_by="fallback",
            )
