"""Business logic for reply-classifier."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError
from nats_client.publisher import Publisher
from reply_classifier.classifier.base import ReplyCategory, Sentiment
from reply_classifier.classifier.composite import CompositeClassifier
from reply_classifier.clients.composer_client import ComposerClient
from reply_classifier.clients.contact_store_client import ContactStoreClient
from reply_classifier.config import Settings
from reply_classifier.events import emit_reply_classified
from reply_classifier.models import Reply
from reply_classifier.repository import ReplyRepository

logger = structlog.get_logger()


class ReplyService:
    def __init__(
        self,
        *,
        repo: ReplyRepository,
        classifier: CompositeClassifier,
        composer_client: ComposerClient,
        contact_store_client: ContactStoreClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._classifier = classifier
        self._composer = composer_client
        self._contact_store = contact_store_client
        self._publisher = publisher
        self._settings = settings

    async def process_incoming_reply(
        self,
        *,
        tenant_id: UUID,
        message_id: UUID,
        from_email: str,
        from_name: str | None,
        subject: str | None,
        body: str,
        received_at: datetime,
        in_reply_to: str | None = None,
        references: str | None = None,
        message_id_header: str | None = None,
        trace_id: str = "",
    ) -> Reply:
        existing = await self._repo.get_by_message_and_email(
            tenant_id=tenant_id, message_id=message_id, from_email=from_email
        )
        if existing is not None:
            logger.info("reply_duplicate_skipped", reply_id=str(existing.id))
            return existing

        original = await self._composer.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=trace_id
        )
        contact_id = UUID(str(original["contact_id"])) if original else None

        body = body[: self._settings.max_body_length]

        classification = await self._classifier.classify(
            tenant_id=str(tenant_id),
            original_message=original or {},
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body=body,
            trace_id=trace_id,
        )

        status = "classified"
        if classification.confidence < self._settings.min_confidence:
            status = "needs_review"

        reply = Reply(
            tenant_id=tenant_id,
            message_id=message_id,
            contact_id=contact_id or message_id,
            channel="email",
            received_at=received_at,
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            raw_content=body,
            language=classification.language,
            in_reply_to=in_reply_to,
            references=references,
            message_id_header=message_id_header,
            classification={
                "category": classification.category.value,
                "confidence": classification.confidence,
                "sentiment": classification.sentiment.value,
                "intent": classification.intent,
                "extracted_questions": classification.extracted_questions,
                "extracted_actions": classification.extracted_actions,
                "classified_by": classification.classified_by,
                "classified_at": datetime.now(UTC).isoformat(),
            },
            category=classification.category.value,
            classification_confidence=classification.confidence,
            suggested_next_action={
                "action": classification.suggested_action.value,
                "reason": classification.suggested_action_reason,
                "draft_reply": None,
            },
            status=status,
        )
        await self._repo.add(reply)
        await self._repo.session.refresh(reply)

        if original is not None:
            await self._sync_message(message_id, tenant_id, reply, trace_id)
            await self._sync_contact(
                contact_id=contact_id,
                tenant_id=tenant_id,
                classification_positive=classification.sentiment == Sentiment.POSITIVE,
                category=classification.category,
                received_at=received_at,
            )

        await emit_reply_classified(self._publisher, reply, trace_id=trace_id)

        logger.info(
            "reply_classified",
            reply_id=str(reply.id),
            message_id=str(message_id),
            category=classification.category.value,
            confidence=classification.confidence,
            action=classification.suggested_action.value,
        )
        return reply

    async def _sync_message(
        self, message_id: UUID, tenant_id: UUID, reply: Reply, trace_id: str
    ) -> None:
        try:
            await self._composer.update_message(
                message_id,
                tenant_id=str(tenant_id),
                payload={
                    "status": "replied",
                    "engagement": {
                        "replied_at": reply.received_at.isoformat(),
                        "reply_id": str(reply.id),
                    },
                },
                trace_id=trace_id,
                idempotency_key=f"reply-classifier:{reply.id}:message",
            )
        except Exception as e:
            logger.warning("composer_update_failed", message_id=str(message_id), error=str(e))

    async def _sync_contact(
        self,
        *,
        contact_id: UUID | None,
        tenant_id: UUID,
        classification_positive: bool,
        category: ReplyCategory,
        received_at: datetime,
    ) -> None:
        if contact_id is None:
            return
        try:
            if category == ReplyCategory.UNSUBSCRIBE:
                await self._contact_store.update_contact_status(
                    contact_id, tenant_id=str(tenant_id), status="unsubscribed"
                )
            elif classification_positive:
                await self._contact_store.update_contact_outreach_history(
                    contact_id,
                    tenant_id=str(tenant_id),
                    replied_positive=True,
                    last_reply_at=received_at,
                )
        except Exception as e:
            logger.warning("contact_update_failed", contact_id=str(contact_id), error=str(e))

    async def get(self, reply_id: UUID) -> Reply:
        r = await self._repo.get(reply_id)
        if r is None:
            raise NotFoundError(f"Reply {reply_id} not found")
        return r

    async def list(self, *, tenant_id: UUID, **kwargs: Any) -> list[Reply]:
        return await self._repo.list(tenant_id=tenant_id, **kwargs)

    async def mark_handled(
        self, *, reply_id: UUID, handled_by: str, outcome: str | None = None
    ) -> Reply:
        reply = await self.get(reply_id)
        reply.status = "handled"
        reply.handled_by = handled_by
        reply.handled_at = datetime.now(UTC)
        reply.outcome = outcome
        await self._repo.session.flush()
        await self._repo.session.refresh(reply)
        return reply

    async def reclassify(self, *, reply_id: UUID, trace_id: str = "") -> Reply:
        reply = await self.get(reply_id)
        original = await self._composer.get_message(
            reply.message_id, tenant_id=str(reply.tenant_id), trace_id=trace_id
        )
        classification = await self._classifier.classify(
            tenant_id=str(reply.tenant_id),
            original_message=original or {},
            from_email=reply.from_email,
            from_name=reply.from_name,
            subject=reply.subject,
            body=reply.raw_content,
            trace_id=trace_id,
        )
        reply.classification = {
            "category": classification.category.value,
            "confidence": classification.confidence,
            "sentiment": classification.sentiment.value,
            "intent": classification.intent,
            "extracted_questions": classification.extracted_questions,
            "extracted_actions": classification.extracted_actions,
            "classified_by": classification.classified_by,
            "classified_at": datetime.now(UTC).isoformat(),
        }
        reply.category = classification.category.value
        reply.classification_confidence = classification.confidence
        reply.suggested_next_action = {
            "action": classification.suggested_action.value,
            "reason": classification.suggested_action_reason,
            "draft_reply": None,
        }
        reply.status = (
            "classified"
            if classification.confidence >= self._settings.min_confidence
            else "needs_review"
        )
        await self._repo.session.flush()
        await self._repo.session.refresh(reply)
        await emit_reply_classified(self._publisher, reply, trace_id=trace_id)
        return reply
