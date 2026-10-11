"""Business logic for composer-service."""

import html as html_lib
from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError, ValidationError
from composer_service.clients.brief_client import BriefClient
from composer_service.clients.contact_store_client import ContactStoreClient
from composer_service.clients.experiments_client import ExperimentsClient
from composer_service.clients.icp_client import ICPClient
from composer_service.config import Settings
from composer_service.events import emit_message_drafted
from composer_service.models import Message
from composer_service.personalization.fact_checker import FactChecker
from composer_service.personalization.personalizer import Personalizer
from composer_service.repository import MessageRepository
from composer_service.schemas import DraftRequest, MessageUpdate
from composer_service.templates.base import TemplateContext
from composer_service.templates.registry import TemplateRegistry
from nats_client.publisher import Publisher

logger = structlog.get_logger()


class ComposerService:
    def __init__(
        self,
        repo: MessageRepository,
        contact_store: ContactStoreClient,
        experiments_client: ExperimentsClient,
        brief_client: BriefClient,
        icp_client: ICPClient,
        template_registry: TemplateRegistry,
        personalizer: Personalizer,
        fact_checker: FactChecker,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._contact_store = contact_store
        self._experiments = experiments_client
        self._brief = brief_client
        self._icp = icp_client
        self._templates = template_registry
        self._personalizer = personalizer
        self._fact_checker = fact_checker
        self._publisher = publisher
        self._settings = settings

    @staticmethod
    def _unwrap(entity: dict[str, Any] | None) -> dict[str, Any] | None:
        """Flatten a contact-store entity: merge ``payload`` with top-level keys."""
        if entity is None:
            return None
        payload = dict(entity.get("payload") or {})
        for key in ("id", "company_id", "status", "fingerprint", "role_category", "seniority"):
            if entity.get(key) is not None:
                payload[key] = entity[key]
        return payload

    async def draft(self, *, tenant_id: UUID, data: DraftRequest, trace_id: str) -> Message:
        contact = self._unwrap(
            await self._contact_store.get_contact(
                data.contact_id, tenant_id=str(tenant_id), trace_id=trace_id
            )
        )
        if contact is None:
            raise NotFoundError(f"Contact {data.contact_id} not found")
        if contact.get("status") in ("unsubscribed", "bounced", "disqualified"):
            raise ValidationError(f"Cannot draft for contact with status {contact['status']}")

        company = None
        company_id = data.company_id or (
            UUID(contact["company_id"]) if contact.get("company_id") else None
        )
        if company_id:
            company = self._unwrap(
                await self._contact_store.get_company(
                    company_id, tenant_id=str(tenant_id), trace_id=trace_id
                )
            )

        icp = await self._icp.get_icp(str(data.icp_id), tenant_id=str(tenant_id), trace_id=trace_id)
        segments = icp.get("payload", {}).get("segments", [])
        segment = next((s for s in segments if s.get("id") == data.segment_id), None)
        if segment is None:
            raise ValidationError(f"Segment {data.segment_id} not found in ICP")

        brief_id = icp.get("brief_id")
        if not brief_id:
            raise ValidationError("ICP has no brief_id")
        brief = await self._brief.get_brief(
            str(brief_id), tenant_id=str(tenant_id), trace_id=trace_id
        )

        variant_id = data.variant_id
        experiment_template_id: str | None = None
        if data.experiment_id and not variant_id:
            try:
                assigned = await self._experiments.assign_variant(
                    experiment_id=data.experiment_id,
                    contact_id=data.contact_id,
                    tenant_id=str(tenant_id),
                    trace_id=trace_id,
                    idempotency_key=(f"composer:assign:{data.experiment_id}:{data.contact_id}"),
                )
                variant_id = assigned.get("variant_id")
                experiment_template_id = assigned.get("template_id")
            except Exception as e:
                logger.warning("experiment_assign_failed", error=str(e))

        if data.template_id:
            template = self._templates.get(data.template_id, data.template_version)
        elif experiment_template_id:
            template = self._templates.get(experiment_template_id, data.template_version)
        else:
            template = self._templates.default_for_channel(data.channel)

        sender = {
            "identity_type": data.sender_identity_type,
            "user_id": data.sender_user_id,
            "from_email": data.sender_from_email,
            "from_name": data.sender_from_name,
            "signature": data.sender_signature,
        }

        parent_message = None
        if data.parent_message_id:
            parent_message = await self._repo.get(data.parent_message_id)

        context = TemplateContext(
            contact=contact,
            company=company,
            sender=sender,
            brief=brief,
            icp=icp,
            segment=segment,
            channel=data.channel,
            language=data.language,
            extra=(
                {"parent_message": self._message_to_dict(parent_message)} if parent_message else {}
            ),
        )
        rendered = template.render(context)

        subject, body, template_warnings = await self._personalizer.generate(
            tenant_id=str(tenant_id),
            rendered=rendered,
            template=template,
            trace_id=trace_id,
        )

        fc_result = self._fact_checker.check(
            body=body, subject=subject, contact=contact, company=company
        )

        recipient_snapshot = self._build_recipient_snapshot(contact, company)
        word_count = len(body.split())

        personalization = {
            "template_id": template.template_id,
            "template_version": template.template_version,
            "segment_id": data.segment_id,
            "icp_id": str(data.icp_id),
            "llm_model": self._settings.llm_model,
            "variables_used": rendered.variables_used,
            "factual_claims": [
                {
                    "claim": c.claim,
                    "evidence_url": c.evidence_url,
                    "confidence": c.confidence,
                    "is_hypothesis": c.is_hypothesis,
                }
                for c in fc_result.claims
            ],
            "warnings": template_warnings + fc_result.warnings,
        }

        experiment = None
        if data.experiment_id:
            experiment = {
                "experiment_id": str(data.experiment_id),
                "variant_id": variant_id,
                "hypothesis": data.hypothesis,
            }

        message = Message(
            tenant_id=tenant_id,
            contact_id=data.contact_id,
            company_id=company_id,
            channel=data.channel,
            status="draft",
            sequence_step=data.sequence_step,
            sequence_total_steps=data.sequence_total_steps,
            parent_message_id=data.parent_message_id,
            is_followup=data.parent_message_id is not None,
            followup_after_days=data.followup_after_days,
            subject=subject,
            body_text=body,
            body_html=self._to_html(body, sender.get("signature")),
            language=data.language,
            word_count=word_count,
            personalization=personalization,
            sender=sender,
            recipient_snapshot=recipient_snapshot,
            experiment=experiment,
            review={},
            delivery={},
            engagement={},
        )
        await self._repo.add(message)
        await self._repo.session.refresh(message)
        await emit_message_drafted(self._publisher, message, trace_id=trace_id)

        logger.info(
            "message_drafted",
            message_id=str(message.id),
            contact_id=str(data.contact_id),
            channel=data.channel,
            template=f"{template.template_id}:{template.template_version}",
            word_count=word_count,
            warnings=len(personalization["warnings"]),
        )
        return message

    async def update(self, message_id: UUID, data: MessageUpdate) -> Message:
        msg = await self.get(message_id)
        if data.subject is not None:
            msg.subject = data.subject
        if data.body_text is not None:
            msg.body_text = data.body_text
            msg.word_count = len(data.body_text.split())
            msg.body_html = self._to_html(data.body_text, (msg.sender or {}).get("signature"))
        if data.status is not None:
            msg.status = data.status
        if data.review is not None:
            msg.review = {**(msg.review or {}), **data.review}
        if data.delivery is not None:
            msg.delivery = {**(msg.delivery or {}), **data.delivery}
        if data.engagement is not None:
            msg.engagement = {**(msg.engagement or {}), **data.engagement}
        if data.sent_at is not None:
            msg.sent_at = data.sent_at
        await self._repo.session.flush()
        await self._repo.session.refresh(msg)
        return msg

    async def get(self, message_id: UUID) -> Message:
        m = await self._repo.get(message_id)
        if m is None:
            raise NotFoundError(f"Message {message_id} not found")
        return m

    async def list(self, *, tenant_id: UUID, **kwargs: Any) -> list[Message]:
        return await self._repo.list(tenant_id=tenant_id, **kwargs)

    def _build_recipient_snapshot(
        self, contact: dict[str, Any], company: dict[str, Any] | None
    ) -> dict[str, Any]:
        primary_email = None
        for e in contact.get("emails", []) or []:
            if e.get("is_primary"):
                primary_email = e.get("value")
                break
        primary_phone = None
        for p in contact.get("phones", []) or []:
            if p.get("is_primary"):
                primary_phone = p.get("value")
                break
        return {
            "email": primary_email,
            "phone": primary_phone,
            "messenger_handle": None,
            "full_name": self._fact_value(contact.get("full_name")) or "",
            "position": self._fact_value(contact.get("position")),
            "company_name": self._fact_value((company or {}).get("name")),
        }

    def _to_html(self, body: str, signature: str | None) -> str:
        safe = html_lib.escape(body)
        paragraphs = safe.split("\n\n")
        return "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip())

    @staticmethod
    def _fact_value(fact: Any) -> str | None:
        if fact is None:
            return None
        if isinstance(fact, str):
            return fact
        if isinstance(fact, dict):
            return fact.get("value")
        return None

    @staticmethod
    def _message_to_dict(m: Message | None) -> dict[str, Any] | None:
        if m is None:
            return None
        return {
            "id": str(m.id),
            "subject": m.subject,
            "body_text": m.body_text,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
