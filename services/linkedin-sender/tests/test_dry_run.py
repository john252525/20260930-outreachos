"""Unit tests for the dry-run client."""

import pytest
from linkedin_sender.clients.dry_run import DryRunClient


@pytest.mark.asyncio
async def test_dry_run_send() -> None:
    client = DryRunClient(account_email="li@example.com")
    result = await client.send_message(handle="in/test", text="hello")
    assert result.success
    assert result.message_id is not None
    await client.close()
