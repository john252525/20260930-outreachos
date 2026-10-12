"""Error classification for retry decisions."""

import httpx


def is_retryable(exc: Exception) -> bool:
    """Client errors (4xx) are terminal; transport/5xx are retryable."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, httpx.TransportError):
        return True
    return True
