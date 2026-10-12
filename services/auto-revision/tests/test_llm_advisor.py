"""Unit tests for LLMAdvisor (fake gateway)."""

from typing import Any

import pytest
from auto_revision.analysis.llm_advisor import LLMAdvisor
from auto_revision.analysis.metrics_analyzer import MetricsSnapshot


class FakeGateway:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def complete_json(self, *, output_schema: type[Any], **kw: Any) -> Any:
        return output_schema.model_validate(self._payload)


@pytest.mark.asyncio
async def test_diagnose_returns_changes() -> None:
    gw = FakeGateway(
        {
            "diagnosis": "Низкий reply rate из-за абстрактной темы",
            "proposed_changes": [
                {
                    "variable_type": "subject",
                    "description": "Добавить конкретику",
                    "example_before": "Предложение",
                    "example_after": "Гидроборты для вашей линейки",
                }
            ],
            "llm_confidence": 0.8,
        }
    )
    advisor = LLMAdvisor(gw)  # type: ignore[arg-type]
    result = await advisor.diagnose(
        tenant_id="t",
        metrics=MetricsSnapshot(sent=100, reply_rate=0.01),
        template_id="email_cold_outreach",
        sample_emails=[],
    )
    assert result["llm_confidence"] == 0.8
    assert len(result["proposed_changes"]) == 1
