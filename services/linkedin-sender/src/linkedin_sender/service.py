"""Business logic for linkedin-sender.

Safety-first: LinkedIn is the riskiest channel. We require (1) global
``LINKEDIN_ENABLED``, (2) per-tenant ``linkedin_enabled`` opt-in, and
(3) an accepted connection (contact.messengers.linkedin.is_connected).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError, ValidationError
from linkedin_sender import events
from linkedin_sender.clients.composer_client import ComposerClient
from linkedin_sender.clients.contact_store_client import ContactStoreClient
from linkedin_sender.clients.factory import build_client
from linkedin_sender.clients.tenant_client import TenantClient
from linkedin_sender.config import Settings
from linkedin_sender.encryptor import SecretEncryptor
from linkedin_sender.models import LinkedInAccount, LinkedInSendAttempt
from linkedin_sender.rampup import LinkedInRateLimiter, WarmUpScheduler
from linkedin_sender.repository import LinkedInRepository
from nats_client.publisher import Publisher

logger = structlog.get_logger()


class LinkedInSenderService:
    def __init__(
        self,
        *,
        repo: LinkedInRepository,
        composer: ComposerClient,
        contact_store: ContactStoreClient,
        tenant_client: TenantClient,
        encryptor: SecretEncryptor,
        limiter: LinkedInRateLimiter,
        scheduler: WarmUpScheduler,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._composer = composer
        self._contact_store = contact_store
        self._tenant = tenant_client
        self._encryptor = encryptor
        self._limiter = limiter
        self._scheduler = scheduler
        self._publisher = publisher
        self._settings = settings

    async def send_approved_message(
        self, *, tenant_id: UUID, message_id: UUID, trace_id: str = ""
    ) -> LinkedInSendAttempt:
        if not self._settings.enabled:
            raise ValidationError("LinkedIn sender is globally disabled")

        tenant_settings = await self._tenant.get_settings(str(tenant_id))
        if not tenant_settings.get("linkedin_enabled", False):
            raise ValidationError("LinkedIn sender not enabled for tenant")

        message = await self._composer.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=trace_id
        )
        if message is None:
            raise NotFoundError(f"Message {message_id} not found")
        if message.get("channel") != "linkedin":
            raise ValidationError("Not a linkedin message")
        if message.get("status") != "approved":
            raise ValidationError(f"Message status is {message.get('status')}, not approved")

        contact_id = message.get("contact_id")
        contact: dict[str, Any] | None = None
        if contact_id:
            contact = await self._contact_store.get_contact(
                UUID(str(contact_id)), tenant_id=str(tenant_id), trace_id=trace_id
            )
        payload = (contact or {}).get("payload") or {}
        li = (payload.get("messengers") or {}).get("linkedin") or {}
        handle = li.get("handle") or (message.get("recipient_snapshot") or {}).get(
            "messenger_handle"
        )
        if not handle:
            raise ValidationError("No LinkedIn handle for contact")
        if not li.get("is_connected", False):
            raise ValidationError("Cannot message — LinkedIn connection not accepted")

        account = await self._repo.select_account(tenant_id)
        if account is None:
            raise ValidationError("No active LinkedIn account")
        if account.status in ("banned", "captcha_required"):
            raise ValidationError(f"account_{account.status}")

        daily, weekly = self._scheduler.compute_limits(account.warmup_started_at)
        can, reason = await self._limiter.can_send(
            account_id=str(account.id),
            daily=min(daily, self._settings.daily_limit_max),
            weekly=min(weekly, self._settings.weekly_limit_max),
        )
        if not can:
            raise ValidationError(f"linkedin_rate_limited:{reason}")

        client = build_client(account, encryptor=self._encryptor, settings=self._settings)
        try:
            result = await client.send_message(
                handle=str(handle), text=message.get("body_text") or ""
            )
        finally:
            await client.close()

        status = "sent"
        error = None
        if not result.success:
            if result.captcha:
                status, error = "captcha_required", "captcha_required"
                account.status = "captcha_required"
                account.last_error = "CAPTCHA detected — requires manual resolution"
            elif result.banned:
                status, error = "banned", "banned"
                account.status = "banned"
                account.ban_detected_at = datetime.now(UTC)
                account.ban_reason = result.error
            else:
                status, error = "failed", result.error

        attempt = LinkedInSendAttempt(
            tenant_id=tenant_id,
            message_id=message_id,
            account_id=account.id,
            status=status,
            to_handle=str(handle),
            provider_message_id=result.message_id,
            error=error,
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
                    "delivery": {"provider_message_id": result.message_id},
                    "sent_at": datetime.now(UTC).isoformat(),
                },
                trace_id=trace_id,
                idempotency_key=f"li:{message_id}:sent",
            )
            await events.emit_message_sent(
                self._publisher,
                tenant_id=tenant_id,
                message_id=message_id,
                sender=account.email,
                provider_message_id=result.message_id,
                trace_id=trace_id,
            )
        else:
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={"status": "failed", "delivery": {"failed_reason": error}},
                trace_id=trace_id,
                idempotency_key=f"li:{message_id}:failed",
            )
            await events.emit_message_failed(
                self._publisher,
                tenant_id=tenant_id,
                message_id=message_id,
                reason=error or "",
                trace_id=trace_id,
            )
            if status == "banned":
                await events.emit_ban_detected(
                    self._publisher,
                    tenant_id=tenant_id,
                    account_id=account.id,
                    reason=error or "banned",
                    trace_id=trace_id,
                )
        await self._repo.session.flush()
        return attempt

    async def create_account(self, *, tenant_id: UUID, data: dict[str, Any]) -> LinkedInAccount:
        account = LinkedInAccount(
            tenant_id=tenant_id,
            user_id=data.get("user_id"),
            email=data["email"],
            password_encrypted=self._encryptor.encrypt(data["password"]),
            cookies_encrypted=(
                self._encryptor.encrypt(data["cookies"]) if data.get("cookies") else None
            ),
            user_agent=data.get("user_agent"),
            proxy_url=data.get("proxy_url"),
            proxy_type=data.get("proxy_type"),
            status="active",
            warmup_started_at=datetime.now(UTC),
        )
        await self._repo.add_account(account)
        await self._repo.session.refresh(account)
        return account

    async def list_accounts(self, tenant_id: UUID) -> list[LinkedInAccount]:
        return await self._repo.list_accounts(tenant_id)

    async def get_account(self, account_id: UUID) -> LinkedInAccount:
        account = await self._repo.get_account(account_id)
        if account is None:
            raise NotFoundError(f"Account {account_id} not found")
        return account

    async def set_account_status(self, account_id: UUID, status: str) -> LinkedInAccount:
        account = await self.get_account(account_id)
        account.status = status
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def verify_account(self, account_id: UUID) -> LinkedInAccount:
        account = await self.get_account(account_id)
        account.last_verified_at = datetime.now(UTC)
        account.last_error = None
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def solve_captcha(self, account_id: UUID) -> LinkedInAccount:
        account = await self.get_account(account_id)
        account.status = "active"
        account.last_error = None
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def list_attempts(self, tenant_id: UUID, *, limit: int = 50) -> list[LinkedInSendAttempt]:
        return await self._repo.list_attempts(tenant_id, limit=limit)
