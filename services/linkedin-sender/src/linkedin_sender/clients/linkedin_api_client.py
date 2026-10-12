"""Real LinkedIn client via the unofficial ``linkedin-api`` library.

Imported lazily: the dependency is optional and only required when real sending
is enabled (LINKEDIN_DRY_RUN=false). The library is synchronous, so calls are
wrapped in a thread executor.
"""

import asyncio
import json
from typing import Any

import structlog

from linkedin_sender.clients.base import SendResult
from linkedin_sender.session.captcha_detector import BanDetector, CaptchaDetector

logger = structlog.get_logger()


class LinkedInApiClient:
    def __init__(
        self,
        *,
        email: str,
        password: str,
        cookies: str | None = None,
        proxy_url: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._cookies = cookies
        self._proxy_url = proxy_url
        self._user_agent = user_agent
        self._client: Any = None

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client

        def _create() -> Any:
            from linkedin_api import Linkedin

            cookies = json.loads(self._cookies) if self._cookies else None
            proxies = (
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            )
            kwargs: dict[str, Any] = {"cookies": cookies}
            if proxies:
                kwargs["proxies"] = proxies
            return Linkedin(self._email, self._password, **kwargs)

        loop = asyncio.get_event_loop()
        self._client = await loop.run_in_executor(None, _create)
        return self._client

    async def send_message(self, *, handle: str, text: str) -> SendResult:
        try:
            client = await self._ensure_client()
            loop = asyncio.get_event_loop()

            def _send() -> Any:
                return client.send_message(text, recipients=[handle])

            result = await loop.run_in_executor(None, _send)
            return SendResult(success=True, message_id=str(result) if result else None)
        except Exception as e:
            text_err = str(e)
            if CaptchaDetector.detect(text_err):
                logger.warning("linkedin_captcha_detected", handle=handle)
                return SendResult(success=False, error="captcha_required", captcha=True)
            if BanDetector.detect(text_err):
                logger.warning("linkedin_ban_detected", handle=handle)
                return SendResult(success=False, error="banned", banned=True)
            logger.warning("linkedin_send_failed", handle=handle, error=text_err)
            return SendResult(success=False, error=text_err)

    async def close(self) -> None:
        self._client = None
