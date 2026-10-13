"""Business logic for whatsapp-sender."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError, ValidationError
from nats_client.publisher import Publisher
from whatsapp_sender import events
from whatsapp_sender.clients.composer_client import ComposerClient
from whatsapp_sender.clients.contact_store_client import ContactStoreClient
from whatsapp_sender.clients.tenant_client import TenantClient
from whatsapp_sender.config import Settings
from whatsapp_sender.encryptor import SecretEncryptor
from whatsapp_sender.models import WhatsAppAccount, WhatsAppSendAttempt, WhatsAppTemplate
from whatsapp_sender.providers.factory import build_provider
from whatsapp_sender.repository import WhatsAppRepository
from whatsapp_sender.session_window import SessionWindowChecker

logger = structlog.get_logger()


class WhatsAppSenderService:
    def __init__(
        self,
        *,
        repo: WhatsAppRepository,
        composer: ComposerClient,
        contact_store: ContactStoreClient,
        tenant_client: TenantClient,
        encryptor: SecretEncryptor,
        window: SessionWindowChecker,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._composer = composer
        self._contact_store = contact_store
        self._tenant = tenant_client
        self._encryptor = encryptor
        self._window = window
        self._publisher = publisher
        self._settings = settings

    async def send_approved_message(
        self, *, tenant_id: UUID, message_id: UUID, trace_id: str = ""
    ) -> WhatsAppSendAttempt:
        if not self._settings.enabled:
            raise ValidationError("WhatsApp sender is globally disabled")

        tenant_settings = await self._tenant.get_settings(str(tenant_id))
        if not tenant_settings.get("whatsapp_enabled", False):
            raise ValidationError("WhatsApp sender not enabled for tenant")

        message = await self._composer.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=trace_id
        )
        if message is None:
            raise NotFoundError(f"Message {message_id} not found")
        if message.get("channel") != "whatsapp":
            raise ValidationError("Not a whatsapp message")
        if message.get("status") != "approved":
            raise ValidationError(f"Message status is {message.get('status')}, not approved")

        contact_id = message.get("contact_id")
        contact: dict[str, Any] | None = None
        if contact_id:
            contact = await self._contact_store.get_contact(
                UUID(str(contact_id)), tenant_id=str(tenant_id), trace_id=trace_id
            )
        consent = (
            ((contact or {}).get("payload") or {})
            .get("consent", {})
            .get("whatsapp_opt_in", "unknown")
        )
        if consent != "granted":
            raise ValidationError("No WhatsApp consent")

        to_phone = (message.get("recipient_snapshot") or {}).get("phone")
        if not to_phone:
            raise ValidationError("No recipient phone in snapshot")

        account = await self._repo.select_account(tenant_id)
        if account is None:
            raise ValidationError("No active WhatsApp account")

        window_open = await self._window.is_open(tenant_id=str(tenant_id), phone=to_phone)
        provider = build_provider(account, encryptor=self._encryptor, settings=self._settings)
        template_id: UUID | None = None
        try:
            if window_open:
                result = await provider.send_text_message(
                    to_phone=to_phone, text=message.get("body_text") or ""
                )
            else:
                template = await self._repo.get_template_to_send(tenant_id)
                if template is None:
                    raise ValidationError("No approved WhatsApp template; window closed")
                template_id = template.id
                result = await provider.send_template_message(
                    to_phone=to_phone,
                    template_name=template.name,
                    language=template.language,
                    variables=[],
                )
        finally:
            await provider.close()

        status = "sent" if result.success else "failed"
        attempt = WhatsAppSendAttempt(
            tenant_id=tenant_id,
            message_id=message_id,
            account_id=account.id,
            status=status,
            to_phone=to_phone,
            template_id=template_id,
            provider_message_id=result.message_id,
            error=result.error,
            sent_at=datetime.now(UTC) if result.success else None,
        )
        await self._repo.add_attempt(attempt)
        if result.success:
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
                idempotency_key=f"wa:{message_id}:sent",
            )
            await events.emit_message_sent(
                self._publisher,
                tenant_id=tenant_id,
                message_id=message_id,
                sender=account.phone_number,
                provider_message_id=result.message_id,
                trace_id=trace_id,
            )
        else:
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={"status": "failed", "delivery": {"failed_reason": result.error}},
                trace_id=trace_id,
                idempotency_key=f"wa:{message_id}:failed",
            )
            await events.emit_message_failed(
                self._publisher,
                tenant_id=tenant_id,
                message_id=message_id,
                reason=result.error or "",
                trace_id=trace_id,
            )
        await self._repo.session.flush()
        return attempt

    async def create_account(self, *, tenant_id: UUID, data: dict[str, Any]) -> WhatsAppAccount:
        account = WhatsAppAccount(
            tenant_id=tenant_id,
            provider=data["provider"],
            phone_number=data["phone_number"],
            provider_account_id=data["provider_account_id"],
            api_key_encrypted=self._encryptor.encrypt(data["api_key"]),
            display_name=data.get("display_name"),
            user_id=data.get("user_id"),
            status="active",
        )
        await self._repo.add_account(account)
        await self._repo.session.refresh(account)
        return account

    async def list_accounts(self, tenant_id: UUID) -> list[WhatsAppAccount]:
        return await self._repo.list_accounts(tenant_id)

    async def verify_account(self, account_id: UUID) -> WhatsAppAccount:
        account = await self._repo.get_account(account_id)
        if account is None:
            raise NotFoundError(f"Account {account_id} not found")
        account.last_verified_at = datetime.now(UTC)
        account.last_error = None
        await self._repo.session.flush()
        await self._repo.session.refresh(account)
        return account

    async def create_template(self, *, tenant_id: UUID, data: dict[str, Any]) -> WhatsAppTemplate:
        template = WhatsAppTemplate(
            tenant_id=tenant_id,
            name=data["name"],
            language=data.get("language", "ru"),
            category=data["category"],
            body_template=data["body_template"],
            variables_count=data.get("variables_count", 0),
            status="approved",
        )
        await self._repo.add_template(template)
        await self._repo.session.refresh(template)
        return template

    async def list_templates(self, tenant_id: UUID) -> list[WhatsAppTemplate]:
        return await self._repo.list_templates(tenant_id)

    async def list_attempts(self, tenant_id: UUID, *, limit: int = 50) -> list[WhatsAppSendAttempt]:
        return await self._repo.list_attempts(tenant_id, limit=limit)

    async def mark_inbound(self, *, tenant_id: UUID, phone: str) -> None:
        await self._window.mark_inbound(tenant_id=str(tenant_id), phone=phone)
