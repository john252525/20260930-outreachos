"""Business logic for sender-email."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError, ValidationError
from nats_client.publisher import Publisher
from sender_email import events
from sender_email.clients.composer_client import ComposerClient
from sender_email.clients.contact_store_client import ContactStoreClient
from sender_email.config import Settings
from sender_email.models import SendAttempt, SenderAccount
from sender_email.rampup.limiter import RampUpLimiter, WarmUpScheduler
from sender_email.repository import SenderRepository
from sender_email.smtp.account_manager import AccountManager, PasswordEncryptor
from sender_email.smtp.client import SendResult, SMTPClient, SMTPConfig

logger = structlog.get_logger()


class RateLimitError(Exception):
    """Raised when no mailbox can send right now (retryable)."""


class SenderService:
    def __init__(
        self,
        *,
        repo: SenderRepository,
        composer: ComposerClient,
        contact_store: ContactStoreClient,
        encryptor: PasswordEncryptor,
        limiter: RampUpLimiter,
        account_manager: AccountManager,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._composer = composer
        self._contact_store = contact_store
        self._encryptor = encryptor
        self._limiter = limiter
        self._account_manager = account_manager
        self._publisher = publisher
        self._settings = settings

    async def send_approved_message(
        self, *, tenant_id: UUID, message_id: UUID, trace_id: str
    ) -> SendAttempt:
        message = await self._composer.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=trace_id
        )
        if message is None:
            raise NotFoundError(f"Message {message_id} not found")
        if message.get("status") != "approved":
            raise ValidationError(f"Message status is {message.get('status')}, not approved")

        to_email = (message.get("recipient_snapshot") or {}).get("email")
        if not to_email:
            raise ValidationError("No recipient email in snapshot")

        blocked, reason = await self._contact_store.check_stoplist(
            tenant_id=str(tenant_id), email=to_email
        )
        if blocked:
            attempt = await self._record_attempt(
                tenant_id=tenant_id,
                message_id=message_id,
                sender_account_id=None,
                to_email=to_email,
                from_email="",
                status="failed",
                error=f"stoplist:{reason}",
            )
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={"status": "failed", "delivery": {"failed_reason": f"stoplist:{reason}"}},
                trace_id=trace_id,
                idempotency_key=f"sender:{message_id}:stoplist",
            )
            return attempt

        sender_info = message.get("sender") or {}
        account = await self._repo.select_account(tenant_id, user_id=sender_info.get("user_id"))
        if account is None:
            raise RateLimitError("no_sender_account")

        can_send, limit_reason = await self._limiter.can_send(account)
        if not can_send:
            raise RateLimitError(limit_reason or "limit")

        if self._settings.dry_run or account.smtp_username == "dry-run":
            logger.info("dry_run_send", to=to_email, message_id=str(message_id))
            result = SendResult(
                success=True, message_id=f"dry-run-{message_id}", response="dry-run", error=None
            )
        else:
            client = SMTPClient(
                SMTPConfig(
                    host=account.smtp_host,
                    port=account.smtp_port,
                    use_ssl=account.smtp_use_ssl,
                    username=account.smtp_username,
                    password=self._encryptor.decrypt(account.smtp_password_encrypted),
                )
            )
            result = await client.send(
                from_email=account.email,
                from_name=account.display_name,
                to_email=to_email,
                subject=message.get("subject") or "",
                body_text=message.get("body_text") or "",
                body_html=message.get("body_html"),
                list_unsubscribe=f"<mailto:unsubscribe@aitler.ru?subject=unsubscribe-{message_id}>",
            )

        attempt = await self._record_attempt(
            tenant_id=tenant_id,
            message_id=message_id,
            sender_account_id=account.id,
            to_email=to_email,
            from_email=account.email,
            status="sent" if result.success else "failed",
            smtp_message_id=result.message_id,
            smtp_response=result.response,
            error=result.error,
            sent_at=datetime.now(UTC) if result.success else None,
        )

        if result.success:
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={
                    "status": "sent",
                    "delivery": {
                        "provider_message_id": result.message_id,
                        "provider_response": {"response": result.response},
                    },
                    "sent_at": datetime.now(UTC).isoformat(),
                },
                trace_id=trace_id,
                idempotency_key=f"sender:{message_id}:sent",
            )
            await self._limiter.record_send(account.id)
            await events.emit_message_sent(
                self._publisher,
                tenant_id=tenant_id,
                message_id=message_id,
                channel=message.get("channel", "email"),
                sender=account.email,
                provider_message_id=result.message_id,
                trace_id=trace_id,
            )
        else:
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={"status": "failed", "delivery": {"failed_reason": result.error}},
                trace_id=trace_id,
                idempotency_key=f"sender:{message_id}:failed",
            )
        return attempt

    # ---- account management ----

    async def create_account(
        self, *, tenant_id: UUID, data: dict[str, Any], user_id: str
    ) -> SenderAccount:
        account = SenderAccount(
            tenant_id=tenant_id,
            user_id=user_id,
            email=data["email"],
            display_name=data.get("display_name"),
            smtp_host=data["smtp_host"],
            smtp_port=data.get("smtp_port", 465),
            smtp_use_ssl=data.get("smtp_use_ssl", True),
            smtp_username=data["smtp_username"],
            smtp_password_encrypted=self._encryptor.encrypt(data["smtp_password"]),
            imap_host=data.get("imap_host") or data["smtp_host"],
            imap_port=data.get("imap_port", 993),
            imap_use_ssl=data.get("imap_use_ssl", True),
            imap_username=data.get("imap_username") or data["smtp_username"],
            imap_password_encrypted=self._encryptor.encrypt(
                data.get("imap_password") or data["smtp_password"]
            ),
            status="unverified",
        )
        await self._repo.add_account(account)
        await self._repo.session.refresh(account)
        return account

    async def verify_account(self, account_id: UUID) -> SenderAccount:
        account = await self._repo.get_account(account_id)
        if account is None:
            raise NotFoundError(f"Account {account_id} not found")
        ok, error = await self._account_manager.verify_connection(account)
        if ok:
            account.status = "active"
            account.last_error = None
            account.last_verified_at = datetime.now(UTC)
            if account.warmup_started_at is None:
                account.warmup_started_at = datetime.now(UTC)
            scheduler = WarmUpScheduler()
            d, h = scheduler.compute_limits(account.warmup_started_at)
            account.daily_limit_current = d
            account.hourly_limit_current = h
        else:
            account.status = "error"
            account.last_error = error
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def set_account_status(self, account_id: UUID, status: str) -> SenderAccount:
        account = await self._repo.get_account(account_id)
        if account is None:
            raise NotFoundError(f"Account {account_id} not found")
        account.status = status
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def delete_account(self, account_id: UUID) -> None:
        account = await self._repo.get_account(account_id)
        if account is None:
            raise NotFoundError(f"Account {account_id} not found")
        await self._repo.session.delete(account)

    async def list_accounts(self, tenant_id: UUID) -> list[SenderAccount]:
        return await self._repo.list_accounts(tenant_id)

    async def get_account(self, account_id: UUID) -> SenderAccount:
        account = await self._repo.get_account(account_id)
        if account is None:
            raise NotFoundError(f"Account {account_id} not found")
        return account

    async def _record_attempt(self, **kwargs: Any) -> SendAttempt:
        attempt = SendAttempt(**kwargs)
        await self._repo.add_attempt(attempt)
        return attempt
