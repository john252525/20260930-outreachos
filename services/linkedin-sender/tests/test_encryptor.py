"""Unit tests for the LinkedIn secret encryptor."""

import base64
import secrets

from linkedin_sender.encryptor import SecretEncryptor


def _key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def test_roundtrip() -> None:
    enc = SecretEncryptor(_key())
    cipher = enc.encrypt("password123")
    assert cipher != "password123"
    assert enc.decrypt(cipher) == "password123"
