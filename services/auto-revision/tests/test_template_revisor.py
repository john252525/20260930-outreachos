"""Unit tests for TemplateRevisor (fake gateway)."""

from typing import Any

import pytest
from auto_revision.analysis.template_revisor import TemplateRevisor


class FakeGateway:
    async def complete_json(self, *, output_schema: type[Any], **kw: Any) -> Any:
        return output_schema.model_validate(
            {
                "system_prompt": "new system",
                "user_prompt_template": "Hello {{ contact_name }}",
                "variables_used": ["contact_name"],
                "summary": "changed subject",
            }
        )


@pytest.mark.asyncio
async def test_revise_returns_template() -> None:
    revisor = TemplateRevisor(FakeGateway())  # type: ignore[arg-type]
    result = await revisor.revise(
        tenant_id="t",
        template_id="email_cold_outreach",
        original_system="old",
        original_user_template="old",
        diagnosis="diag",
        proposed_changes=[],
    )
    assert result["system_prompt"] == "new system"
    assert "{{ contact_name }}" in str(result["user_prompt_template"])
