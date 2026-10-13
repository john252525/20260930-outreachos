"""JWT token service."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from users_service.config import Settings


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret
        self._algorithm = "HS256"
        self._expires_minutes = settings.jwt_expires_minutes

    def create_access_token(
        self,
        *,
        user_id: UUID,
        email: str,
        tenant_id: UUID,
        role: str,
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(minutes=self._expires_minutes)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "email": email,
            "tenant_id": str(tenant_id),
            "role": role,
            "exp": expires_at,
            "iat": datetime.now(UTC),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def decode_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self._secret, algorithms=[self._algorithm])
