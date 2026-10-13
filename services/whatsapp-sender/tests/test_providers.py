"""Unit tests for WhatsApp providers."""

import pytest
from whatsapp_sender.providers.dry_run import DryRunProvider


@pytest.mark.asyncio
async def test_dry_run_text() -> None:
    p = DryRunProvider()
    r = await p.send_text_message(to_phone="+7", text="hi")
    assert r.success
    assert r.message_id is not None


@pytest.mark.asyncio
async def test_dry_run_template() -> None:
    p = DryRunProvider()
    r = await p.send_template_message(
        to_phone="+7", template_name="t", language="ru", variables=[]
    )
    assert r.success
