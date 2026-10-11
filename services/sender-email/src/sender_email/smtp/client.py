"""Async SMTP client."""

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import aiosmtplib
import structlog

logger = structlog.get_logger()


@dataclass
class SMTPConfig:
    host: str
    port: int
    use_ssl: bool
    username: str
    password: str


@dataclass
class SendResult:
    success: bool
    message_id: str | None
    response: str | None
    error: str | None


class SMTPClient:
    """Async SMTP client. One instance per send."""

    def __init__(self, config: SMTPConfig, *, timeout: float = 30.0) -> None:
        self._config = config
        self._timeout = timeout

    async def send(
        self,
        *,
        from_email: str,
        from_name: str | None,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        reply_to: str | None = None,
        list_unsubscribe: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> SendResult:
        msg = EmailMessage()
        msg["From"] = formataddr((from_name or "", from_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        if list_unsubscribe:
            msg["List-Unsubscribe"] = list_unsubscribe
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        domain = from_email.split("@")[1] if "@" in from_email else "example.com"
        msg_id = make_msgid(domain=domain)
        msg["Message-ID"] = msg_id

        if headers:
            for k, v in headers.items():
                msg[k] = v

        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        try:
            if self._config.use_ssl:
                smtp = aiosmtplib.SMTP(
                    hostname=self._config.host,
                    port=self._config.port,
                    use_tls=True,
                    timeout=self._timeout,
                )
            else:
                smtp = aiosmtplib.SMTP(
                    hostname=self._config.host,
                    port=self._config.port,
                    start_tls=True,
                    timeout=self._timeout,
                )
            await smtp.connect()
            await smtp.login(self._config.username, self._config.password)
            response = await smtp.send_message(msg)
            await smtp.quit()
            logger.info("smtp_sent", to=to_email, msg_id=msg_id)
            return SendResult(success=True, message_id=msg_id, response=str(response), error=None)
        except Exception as e:
            logger.warning("smtp_failed", to=to_email, error=str(e))
            return SendResult(success=False, message_id=None, response=None, error=str(e))


async def verify_smtp(config: SMTPConfig, *, timeout: float = 15.0) -> tuple[bool, str | None]:
    """Verify SMTP login without sending."""
    try:
        if config.use_ssl:
            smtp = aiosmtplib.SMTP(
                hostname=config.host, port=config.port, use_tls=True, timeout=timeout
            )
        else:
            smtp = aiosmtplib.SMTP(
                hostname=config.host, port=config.port, start_tls=True, timeout=timeout
            )
        await smtp.connect()
        await smtp.login(config.username, config.password)
        await smtp.quit()
        return True, None
    except Exception as e:
        return False, str(e)
