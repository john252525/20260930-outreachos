"""Business logic for review-queue."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from common.errors import NotFoundError, ValidationError
from nats_client.publisher import Publisher
from review_queue import events
from review_queue.clients.composer_client import ComposerClient
from review_queue.models import ReviewItem
from review_queue.repository import ReviewItemRepository

logger = structlog.get_logger()


class ReviewQueueService:
    def __init__(
        self,
        repo: ReviewItemRepository,
        composer: ComposerClient,
        publisher: Publisher,
    ) -> None:
        self._repo = repo
        self._composer = composer
        self._publisher = publisher

    async def create_from_message(
        self, *, tenant_id: UUID, message_id: UUID, trace_id: str = ""
    ) -> ReviewItem | None:
        """Create a review item from a message (idempotent by message_id)."""
        existing = await self._repo.get_by_message(tenant_id, message_id)
        if existing is not None:
            return existing

        message = await self._composer.get_message(
            message_id, tenant_id=str(tenant_id), trace_id=trace_id
        )
        if message is None:
            logger.warning("review_message_not_found", message_id=str(message_id))
            return None

        personalization = message.get("personalization") or {}
        warnings = personalization.get("warnings") or []
        claims = personalization.get("factual_claims") or []
        hypotheses = sum(1 for c in claims if c.get("is_hypothesis"))

        body = message.get("body_text") or ""
        priority = "high" if (warnings or hypotheses) else "normal"

        snapshot = {
            "subject": message.get("subject"),
            "body_preview": body[:500],
            "warnings": warnings,
            "factual_claims_count": len(claims),
            "hypotheses_count": hypotheses,
        }

        item = ReviewItem(
            tenant_id=tenant_id,
            message_id=message_id,
            contact_id=UUID(message["contact_id"]),
            channel=message.get("channel", "email"),
            status="pending",
            priority=priority,
            snapshot=snapshot,
        )
        await self._repo.add(item)
        await self._repo.session.refresh(item)
        logger.info(
            "review_item_created",
            item_id=str(item.id),
            message_id=str(message_id),
            priority=priority,
        )
        return item

    async def approve(
        self,
        *,
        tenant_id: UUID,
        item_id: UUID,
        user_id: str,
        scheduled_send_at: datetime | None,
        trace_id: str,
    ) -> ReviewItem:
        item = await self._get(item_id)
        if item.status != "pending":
            raise ValidationError(f"Cannot approve item with status {item.status}")

        edited = item.edit is not None
        review: dict[str, Any] = {
            "reviewed_by": user_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        if edited:
            review["edited_by_human"] = True
            review["original_body_text"] = (item.edit or {}).get("body_before")

        message = await self._composer.update_message(
            item.message_id,
            tenant_id=str(tenant_id),
            payload={"status": "approved", "review": review},
            trace_id=trace_id,
            idempotency_key=f"review:{item.id}:approve",
        )

        item.status = "edited_and_approved" if edited else "approved"
        item.reviewed_by = user_id
        item.reviewed_at = datetime.now(UTC)
        item.scheduled_send_at = scheduled_send_at
        await self._repo.session.flush()
        await self._repo.session.refresh(item)
        await events.emit_message_approved(self._publisher, item, message, trace_id=trace_id)
        return item

    async def reject(
        self,
        *,
        tenant_id: UUID,
        item_id: UUID,
        user_id: str,
        reason: str,
        note: str | None,
        trace_id: str,
    ) -> ReviewItem:
        item = await self._get(item_id)
        if item.status != "pending":
            raise ValidationError(f"Cannot reject item with status {item.status}")

        await self._composer.update_message(
            item.message_id,
            tenant_id=str(tenant_id),
            payload={
                "status": "rejected",
                "review": {
                    "reviewed_by": user_id,
                    "reviewed_at": datetime.now(UTC).isoformat(),
                    "rejection_reason": reason,
                },
            },
            trace_id=trace_id,
            idempotency_key=f"review:{item.id}:reject",
        )

        item.status = "rejected"
        item.reviewed_by = user_id
        item.reviewed_at = datetime.now(UTC)
        item.rejection = {
            "reason": reason,
            "note": note,
            "rejected_at": datetime.now(UTC).isoformat(),
            "rejected_by": user_id,
        }
        await self._repo.session.flush()
        await self._repo.session.refresh(item)
        await events.emit_message_rejected(self._publisher, item, trace_id=trace_id)
        return item

    async def edit(
        self,
        *,
        tenant_id: UUID,
        item_id: UUID,
        subject: str | None,
        body_text: str,
        user_id: str,
        trace_id: str,
    ) -> ReviewItem:
        item = await self._get(item_id)
        if item.status != "pending":
            raise ValidationError(f"Cannot edit item with status {item.status}")

        message = await self._composer.get_message(
            item.message_id, tenant_id=str(tenant_id), trace_id=trace_id
        )
        body_before = (message or {}).get("body_text")
        subject_before = (message or {}).get("subject")

        await self._composer.update_message(
            item.message_id,
            tenant_id=str(tenant_id),
            payload={"subject": subject, "body_text": body_text},
            trace_id=trace_id,
            idempotency_key=f"review:{item.id}:edit:{hash(body_text) & 0xFFFFFFFF}",
        )

        item.edit = {
            "edited_at": datetime.now(UTC).isoformat(),
            "edited_by": user_id,
            "diff": {
                "subject_before": subject_before,
                "subject_after": subject,
                "body_before": body_before,
                "body_after": body_text,
            },
        }
        item.snapshot = {
            **(item.snapshot or {}),
            "subject": subject,
            "body_preview": body_text[:500],
        }
        await self._repo.session.flush()
        await self._repo.session.refresh(item)
        return item

    async def assign(self, *, item_id: UUID, assigned_to: str) -> ReviewItem:
        item = await self._get(item_id)
        item.assigned_to = assigned_to
        await self._repo.session.flush()
        await self._repo.session.refresh(item)
        return item

    async def bulk_approve(
        self, *, tenant_id: UUID, item_ids: list[UUID], user_id: str, trace_id: str
    ) -> dict[str, Any]:
        approved = 0
        errors: list[dict[str, Any]] = []
        for iid in item_ids:
            try:
                await self.approve(
                    tenant_id=tenant_id,
                    item_id=iid,
                    user_id=user_id,
                    scheduled_send_at=None,
                    trace_id=trace_id,
                )
                approved += 1
            except Exception as e:
                errors.append({"item_id": str(iid), "error": str(e)})
        return {"approved": approved, "errors": errors}

    async def get(self, item_id: UUID) -> ReviewItem:
        return await self._get(item_id)

    async def list(
        self,
        *,
        tenant_id: UUID,
        status: str | None,
        priority: str | None,
        assigned_to: str | None,
        limit: int,
        offset: int,
    ) -> list[ReviewItem]:
        return await self._repo.list(
            tenant_id=tenant_id,
            status=status,
            priority=priority,
            assigned_to=assigned_to,
            limit=limit,
            offset=offset,
        )

    async def _get(self, item_id: UUID) -> ReviewItem:
        item = await self._repo.get(item_id)
        if item is None:
            raise NotFoundError(f"Review item {item_id} not found")
        return item
