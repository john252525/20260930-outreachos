"""Unit tests for the secret encryptor."""

import base64
import secrets

from telegram_sender.crypto.encryptor import SecretEncryptor


def _key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def test_encrypt_decrypt_roundtrip() -> None:
    enc = SecretEncryptor(_key())
    token = "123456:ABC-DEF"
    cipher = enc.encrypt(token)
    assert cipher != token
    assert enc.decrypt(cipher) == token


def test_different_keys_cannot_decrypt() -> None:
    a = SecretEncryptor(_key())
    b = SecretEncryptor(_key())
    cipher = a.encrypt("secret")
    try:
        b.decrypt(cipher)
        raise AssertionError("should have raised")
    except Exception:
        pass
