"""Business logic for telegram-sender."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError, ValidationError
from nats_client.publisher import Publisher
from telegram_sender import events
from telegram_sender.clients.composer_client import ComposerClient
from telegram_sender.clients.contact_store_client import ContactStoreClient
from telegram_sender.config import Settings
from telegram_sender.crypto.encryptor import SecretEncryptor
from telegram_sender.models import TelegramAccount, TelegramSendAttempt
from telegram_sender.rampup import TelegramRateLimiter, WarmUpScheduler
from telegram_sender.repository import TelegramRepository

logger = structlog.get_logger()


class TelegramSenderService:
    def __init__(
        self,
        *,
        repo: TelegramRepository,
        composer: ComposerClient,
        contact_store: ContactStoreClient,
        encryptor: SecretEncryptor,
        limiter: TelegramRateLimiter,
        scheduler: WarmUpScheduler,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._composer = composer
        self._contact_store = contact_store
        self._encryptor = encryptor
        self._limiter = limiter
        self._scheduler = scheduler
        self._publisher = publisher
        self._settings = settings

    async def send_approved_message(
        self, *, tenant_id: UUID, message_id: UUID, trace_id: str = ""
    ) -> TelegramSendAttempt:
        message = await self._composer.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=trace_id
        )
        if message is None:
            raise NotFoundError(f"Message {message_id} not found")
        if message.get("channel") != "telegram":
            raise ValidationError("Not a telegram message")
        if message.get("status") != "approved":
            raise ValidationError(f"Message status is {message.get('status')}, not approved")

        contact_id = message.get("contact_id")
        contact = None
        if contact_id:
            contact = await self._contact_store.get_contact(
                UUID(str(contact_id)), tenant_id=str(tenant_id), trace_id=trace_id
            )
        payload = (contact or {}).get("payload") or {}
        consent = (payload.get("consent") or {}).get("messenger_opt_in", "unknown")
        replied_positive = bool((contact or {}).get("replied_positive"))
        if consent != "granted" and not replied_positive:
            raise ValidationError("Cannot send cold telegram — no consent, no prior reply")

        snapshot = message.get("recipient_snapshot") or {}
        handle = snapshot.get("messenger_handle")
        if not handle:
            raise ValidationError("No messenger_handle in recipient snapshot")

        account = await self._repo.select_account(tenant_id)
        if account is None:
            raise ValidationError("No active telegram account")

        if account.flood_wait_until is not None and account.flood_wait_until > datetime.now(UTC):
            raise ValidationError("account_in_flood_wait")

        daily, hourly = self._scheduler.compute_limits(account.warmup_started_at)
        can, reason = await self._limiter.can_send(
            account_id=str(account.id),
            daily=min(daily, self._settings.daily_limit_max),
            hourly=min(hourly, self._settings.hourly_limit_max),
        )
        if not can:
            raise ValidationError(f"telegram_rate_limited:{reason}")

        result = await self._dispatch(
            account=account, handle=str(handle), text=message.get("body_text") or ""
        )

        status = "sent"
        error = None
        flood = None
        if not result.get("success"):
            error = str(result.get("error", "unknown"))
            flood = result.get("flood_wait_seconds")
            status = "flood_wait" if error == "flood_wait" else "failed"

        attempt = TelegramSendAttempt(
            tenant_id=tenant_id,
            message_id=message_id,
            account_id=account.id,
            status=status,
            to_handle=str(handle),
            to_chat_id=result.get("chat_id"),
            telegram_message_id=(
                str(result["message_id"]) if result.get("message_id") is not None else None
            ),
            error=error,
            flood_wait_seconds=flood if isinstance(flood, int) else None,
            sent_at=datetime.now(UTC) if status == "sent" else None,
        )
        await self._repo.add_attempt(attempt)

        if status == "sent":
            await self._limiter.record_send(account_id=str(account.id))
            account.daily_sent_today += 1
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={
                    "status": "sent",
                    "delivery": {"provider_message_id": str(result.get("message_id"))},
                    "sent_at": datetime.now(UTC).isoformat(),
                },
                trace_id=trace_id,
                idempotency_key=f"tg:{message_id}:sent",
            )
            await events.emit_message_sent(
                self._publisher,
                tenant_id=tenant_id,
                message_id=message_id,
                channel="telegram",
                sender=account.bot_username or account.phone or "telegram",
                provider_message_id=str(result.get("message_id")),
                trace_id=trace_id,
            )
        else:
            if flood is not None and isinstance(flood, int):
                account.status = "flood_wait"
                account.flood_wait_until = datetime.now(UTC).replace(microsecond=0) + timedelta(
                    seconds=flood
                )
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={"status": "failed", "delivery": {"failed_reason": error}},
                trace_id=trace_id,
                idempotency_key=f"tg:{message_id}:failed",
            )
            await events.emit_message_failed(
                self._publisher,
                tenant_id=tenant_id,
                message_id=message_id,
                reason=error or "unknown",
                trace_id=trace_id,
            )
        await self._repo.session.flush()
        return attempt

    async def _dispatch(
        self, *, account: TelegramAccount, handle: str, text: str
    ) -> dict[str, Any]:
        if (
            self._settings.dry_run
            and account.account_type == "bot"
            and not account.bot_token_encrypted
        ):
            logger.info("dry_run_telegram", to=handle, account_id=str(account.id))
            return {"success": True, "message_id": f"dry-run-{account.id}", "chat_id": handle}
        if self._settings.dry_run:
            logger.info("dry_run_telegram", to=handle, account_id=str(account.id))
            return {"success": True, "message_id": f"dry-run-{account.id}", "chat_id": handle}

        if account.account_type == "bot" and account.bot_token_encrypted:
            from telegram_sender.clients.bot_client import BotClient

            token = self._encryptor.decrypt(account.bot_token_encrypted)
            bot = BotClient(token)
            try:
                return await bot.send(chat_id=handle, text=text)
            finally:
                await bot.close()
        if account.account_type == "mtproto" and account.session_string_encrypted:
            from telegram_sender.clients.mtproto_client import MTProtoClient

            mt = MTProtoClient(
                api_id=account.api_id or 0,
                api_hash=self._encryptor.decrypt(account.api_hash_encrypted or ""),
                session_string=self._encryptor.decrypt(account.session_string_encrypted),
            )
            try:
                return await mt.send(peer=handle, text=text)
            finally:
                await mt.close()
        return {"success": False, "error": "no_credentials"}

    # ---- accounts ----

    async def create_account(self, *, tenant_id: UUID, data: dict[str, Any]) -> TelegramAccount:
        account = TelegramAccount(
            tenant_id=tenant_id,
            account_type=data["account_type"],
            display_name=data.get("display_name"),
            user_id=data.get("user_id"),
            status="active",
            warmup_started_at=datetime.now(UTC),
        )
        if data["account_type"] == "bot":
            if not data.get("bot_token"):
                raise ValidationError("bot_token required for bot account")
            account.bot_token_encrypted = self._encryptor.encrypt(data["bot_token"])
            account.bot_username = data.get("bot_username")
        else:
            if not data.get("session_string") or data.get("api_id") is None:
                raise ValidationError("api_id and session_string required for mtproto account")
            account.api_id = data.get("api_id")
            account.api_hash_encrypted = self._encryptor.encrypt(data.get("api_hash") or "")
            account.phone = data.get("phone")
            account.session_string_encrypted = self._encryptor.encrypt(data["session_string"])

        await self._repo.add_account(account)
        await self._repo.session.refresh(account)
        return account

    async def list_accounts(self, tenant_id: UUID) -> list[TelegramAccount]:
        return await self._repo.list_accounts(tenant_id)

    async def get_account(self, account_id: UUID) -> TelegramAccount:
        account = await self._repo.get_account(account_id)
        if account is None:
            raise NotFoundError(f"Account {account_id} not found")
        return account

    async def set_account_status(self, account_id: UUID, status: str) -> TelegramAccount:
        account = await self.get_account(account_id)
        account.status = status
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def verify_account(self, account_id: UUID) -> TelegramAccount:
        account = await self.get_account(account_id)
        account.last_verified_at = datetime.now(UTC)
        account.last_error = None
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def list_attempts(self, tenant_id: UUID, *, limit: int = 50) -> list[TelegramSendAttempt]:
        return await self._repo.list_attempts(tenant_id, limit=limit)
