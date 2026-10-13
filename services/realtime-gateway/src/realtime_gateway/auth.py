"""JWT verification for WebSocket connections."""

from typing import Any

import jwt


def decode_token(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])
