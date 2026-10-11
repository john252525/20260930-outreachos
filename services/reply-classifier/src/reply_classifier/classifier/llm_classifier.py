"""LLM-based classifier for non-obvious replies."""

from typing import Any

import structlog

from reply_classifier.classifier.base import (
    ClassificationResult,
    NextAction,
    ReplyCategory,
    Sentiment,
)
from reply_classifier.llm.client import LLMClient
from reply_classifier.llm.prompts.classify_reply import build_classify_prompt
from reply_classifier.llm.schemas import LLMClassification

logger = structlog.get_logger()


class LLMClassifier:
    def __init__(self, llm: LLMClient, *, max_body_length: int = 10_000) -> None:
        self._llm = llm
        self._max_body_length = max_body_length

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
        prompt = build_classify_prompt(
            original_from=(original_message.get("sender") or {}).get("from_email") or "",
            original_subject=original_message.get("subject") or "",
            original_body=original_message.get("body_text") or "",
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body=body,
            max_body_length=self._max_body_length,
        )

        result: LLMClassification = await self._llm.complete_json(
            tenant_id=tenant_id,
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=LLMClassification,
            trace_id=trace_id,
            temperature=0.1,
            max_tokens=1024,
        )

        logger.info(
            "reply_llm_classified",
            category=result.category,
            confidence=result.confidence,
            language=result.language,
        )

        return ClassificationResult(
            category=ReplyCategory(result.category),
            confidence=result.confidence,
            sentiment=Sentiment(result.sentiment),
            intent=result.intent,
            extracted_questions=result.extracted_questions,
            extracted_actions=result.extracted_actions,
            suggested_action=NextAction(result.suggested_action),
            suggested_action_reason=result.suggested_action_reason,
            classified_by=f"llm:{self._llm.model_name}",
            language=result.language,
        )
