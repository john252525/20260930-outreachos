"""Unit tests for retry classification."""

import httpx
from orchestrator.errors import is_retryable


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://x/y")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


def test_4xx_is_terminal() -> None:
    assert is_retryable(_status_error(422)) is False
    assert is_retryable(_status_error(404)) is False


def test_5xx_is_retryable() -> None:
    assert is_retryable(_status_error(500)) is True
    assert is_retryable(_status_error(503)) is True


def test_transport_error_is_retryable() -> None:
    assert is_retryable(httpx.ConnectError("nope")) is True
