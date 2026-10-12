"""LinkedIn client abstraction."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    captcha: bool = False
    banned: bool = False


class LinkedInClient(Protocol):
    async def send_message(self, *, handle: str, text: str) -> SendResult: ...

    async def close(self) -> None: ...
