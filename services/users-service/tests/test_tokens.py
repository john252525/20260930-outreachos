"""Unit tests for JWT token service."""

from uuid import uuid4

from users_service.auth.tokens import TokenService
from users_service.config import Settings


def _settings() -> Settings:
    return Settings(
        SERVICE_NAME="users-service",
        DATABASE_URL="postgresql+asyncpg://x:y@localhost/db",
        NATS_URL="nats://localhost:4222",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-key",
    )


def test_token_roundtrip() -> None:
    svc = TokenService(_settings())
    uid = uuid4()
    tid = uuid4()
    token, _expires = svc.create_access_token(
        user_id=uid, email="a@b.com", tenant_id=tid, role="admin"
    )
    payload = svc.decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["tenant_id"] == str(tid)
    assert payload["role"] == "admin"
