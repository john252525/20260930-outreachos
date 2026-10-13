"""Unit tests for Argon2 password hashing."""

from users_service.auth.password import hash_password, needs_rehash, verify_password


def test_hash_and_verify() -> None:
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_needs_rehash_false_for_fresh() -> None:
    h = hash_password("secret123")
    assert needs_rehash(h) is False
