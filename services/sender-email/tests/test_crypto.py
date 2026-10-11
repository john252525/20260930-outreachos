"""Unit tests for password encryption."""

from cryptography.fernet import Fernet
from sender_email.smtp.account_manager import PasswordEncryptor


def test_encrypt_decrypt_roundtrip():
    key = Fernet.generate_key().decode()
    enc = PasswordEncryptor(key)
    ct = enc.encrypt("super-secret")
    assert ct != "super-secret"
    assert enc.decrypt(ct) == "super-secret"
