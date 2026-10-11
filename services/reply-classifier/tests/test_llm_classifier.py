"""Unit tests for the LLM classifier (with a fake gateway client)."""

from typing import Any

import pytest
from pydantic import ValidationError
from reply_classifier.classifier.base import NextAction, ReplyCategory
from reply_classifier.classifier.llm_classifier import LLMClassifier
from reply_classifier.llm.schemas import LLMClassification


class FakeGateway:
    """Stand-in for LLMClient.complete_json."""

    def __init__(self, payload: dict[str, Any], *, boom: bool = False) -> None:
        self.model_name = "deepseek-flash"
        self._payload = payload
        self._boom = boom
        self.last_task_type: str | None = None

    async def complete_json(
        self, *, task_type: str, output_schema: type[Any], **kwargs: Any
    ) -> Any:
        self.last_task_type = task_type
        if self._boom:
            raise RuntimeError("gateway boom")
        return output_schema.model_validate(self._payload)


@pytest.mark.asyncio
async def test_llm_classifier_maps_result() -> None:
    gw = FakeGateway(
        {
            "category": "question",
            "confidence": 0.88,
            "sentiment": "positive",
            "intent": "asks price",
            "extracted_questions": ["Какая цена?"],
            "extracted_actions": ["прислать прайс"],
            "suggested_action": "reply",
            "suggested_action_reason": "ждёт ответа",
            "language": "ru",
        }
    )
    clf = LLMClassifier(gw)  # type: ignore[arg-type]
    result = await clf.classify(
        tenant_id="t",
        original_message={"sender": {"from_email": "a@b.com"}, "subject": "S", "body_text": "B"},
        from_email="x@y.com",
        from_name="Иван",
        subject="Re: S",
        body="Какая цена?",
    )
    assert result.category == ReplyCategory.QUESTION
    assert result.confidence == 0.88
    assert result.suggested_action == NextAction.REPLY
    assert result.classified_by == "llm:deepseek-flash"
    assert result.extracted_questions == ["Какая цена?"]
    assert gw.last_task_type == "reply_classify_v1"


@pytest.mark.asyncio
async def test_llm_classifier_unknown_ok() -> None:
    gw = FakeGateway(
        {
            "category": "unknown",
            "confidence": 0.3,
            "sentiment": "neutral",
            "suggested_action": "forward_to_human",
        }
    )
    clf = LLMClassifier(gw)  # type: ignore[arg-type]
    result = await clf.classify(
        tenant_id="t",
        original_message={},
        from_email="x@y.com",
        from_name=None,
        subject=None,
        body="...",
    )
    assert result.category == ReplyCategory.UNKNOWN


def test_schema_rejects_bad_category() -> None:
    with pytest.raises(ValidationError):
        LLMClassification.model_validate(
            {
                "category": "banana",
                "confidence": 0.5,
                "sentiment": "neutral",
                "suggested_action": "reply",
            }
        )
