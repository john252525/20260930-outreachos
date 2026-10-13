"""Password hashing with Argon2."""

import contextlib

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)

# Precomputed dummy hash for constant-time auth when user not found.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hash_: str) -> bool:
    try:
        _hasher.verify(hash_, password)
        return True
    except (VerifyMismatchError, VerificationError):
        return False


def verify_dummy(password: str) -> None:
    """Constant-time guard: run a verification even when the user is missing."""
    with contextlib.suppress(Exception):
        _hasher.verify(_DUMMY_HASH, password)


def needs_rehash(hash_: str) -> bool:
    return _hasher.check_needs_rehash(hash_)
