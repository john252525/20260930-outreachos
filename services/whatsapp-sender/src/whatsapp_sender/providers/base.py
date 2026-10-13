"""WhatsApp provider abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


class WhatsAppProvider(ABC):
    name: str

    @abstractmethod
    async def send_text_message(self, *, to_phone: str, text: str) -> SendResult: ...

    @abstractmethod
    async def send_template_message(
        self, *, to_phone: str, template_name: str, language: str, variables: list[str]
    ) -> SendResult: ...

    async def close(self) -> None:
        return None
