"""Detects LinkedIn captcha / checkpoint challenges.

When detected we NEVER try to bypass automatically — the account is paused
and a human must resolve it.
"""

from typing import ClassVar

PATTERNS = [
    "checkpoint/challenge",
    "captcha",
    "security verification",
    "unusual activity",
    "we've restricted",
    "account restricted",
]


class CaptchaDetector:
    @classmethod
    def detect(cls, text: str) -> bool:
        lower = (text or "").lower()
        return any(p in lower for p in PATTERNS)


class BanDetector:
    PATTERNS: ClassVar[list[str]] = ["account has been restricted", "we have restricted", "banned"]

    @classmethod
    def detect(cls, text: str) -> bool:
        lower = (text or "").lower()
        return any(p in lower for p in cls.PATTERNS)
