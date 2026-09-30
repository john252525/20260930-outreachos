"""Business logic for brief-service."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from brief_service import events
from brief_service.config import Settings
from brief_service.fetcher import fetch_websites
from brief_service.llm.client import LLMClient
from brief_service.llm.prompts.extract_brief import build_extract_prompt
from brief_service.llm.prompts.generate_questions import build_generate_questions_prompt
from brief_service.llm.schemas import ExtractSchema, QuestionsSchema
from brief_service.models import Brief
from brief_service.repository import BriefRepository
from brief_service.scoring.completeness import compute_completeness
from brief_service.scoring.missing_info import analyze_missing_info, get_next_priority_field
from common.errors import NotFoundError, ValidationError
from nats_client.publisher import Publisher

logger = structlog.get_logger()


class BriefService:
    def __init__(
        self,
        repo: BriefRepository,
        llm: LLMClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._llm = llm
        self._publisher = publisher
        self._settings = settings

    async def create_from_raw_input(
        self,
        *,
        tenant_id: UUID,
        text: str | None,
        urls: list[str],
        transcript: str | None,
        created_by: str,
        trace_id: str,
    ) -> Brief:
        if not (text or urls or transcript):
            raise ValidationError("At least one of text/urls/transcript is required")

        website_contents = await fetch_websites(urls)

        prompt = build_extract_prompt(
            raw_text=text,
            urls=urls,
            transcript=transcript,
            website_contents=website_contents,
        )
        extracted = await self._llm.complete_json(
            tenant_id=str(tenant_id),
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=ExtractSchema,
            trace_id=trace_id,
        )

        data = {
            "identity": extracted.identity.model_dump(),
            "offering": extracted.offering.model_dump(),
            "targeting_hints": extracted.targeting_hints.model_dump(),
            "outreach_goals": extracted.outreach_goals.model_dump(),
        }
        completeness = compute_completeness(data)
        missing = analyze_missing_info(data)

        brief = Brief(
            tenant_id=tenant_id,
            status="in_progress"
            if completeness < self._settings.completeness_threshold
            else "complete",
            completeness_score=completeness,
            raw_input={
                "text": text,
                "urls": urls,
                "transcript": transcript,
                "website_contents": [
                    {"url": w["url"], "title": w["title"]} for w in website_contents
                ],
                "submitted_at": datetime.now(UTC).isoformat(),
            },
            qa_history=[],
            identity=data["identity"],
            offering=data["offering"],
            targeting_hints=data["targeting_hints"],
            outreach_goals=data["outreach_goals"],
            missing_info=missing,
            created_by=created_by,
            trace_id=trace_id,
        )
        await self._repo.add(brief)
        await self._repo.session.refresh(brief)
        await events.emit_brief_created(self._publisher, brief, trace_id=trace_id)

        if brief.status != "complete":
            await self._generate_and_append_question(brief, trace_id=trace_id)
        else:
            await events.emit_brief_completed(self._publisher, brief, trace_id=trace_id)

        return brief

    async def answer_question(
        self,
        *,
        brief_id: UUID,
        question_index: int,
        answer: str,
        trace_id: str,
    ) -> Brief:
        brief = await self._repo.get(brief_id)
        if brief is None:
            raise NotFoundError(f"Brief {brief_id} not found")

        qa = list(brief.qa_history or [])
        if question_index < 0 or question_index >= len(qa):
            raise ValidationError(f"Question index {question_index} out of range")

        item = dict[str, Any](qa[question_index])
        if item.get("answered_at") is not None:
            raise ValidationError(f"Question {question_index} already answered")
        item["answer"] = answer
        item["answered_at"] = datetime.now(UTC).isoformat()
        qa[question_index] = item
        brief.qa_history = qa

        await self._re_extract(brief, trace_id=trace_id)

        data = self._brief_data(brief)
        brief.completeness_score = compute_completeness(data)
        brief.missing_info = analyze_missing_info(data)

        if brief.completeness_score >= self._settings.completeness_threshold:
            brief.status = "complete"
            await self._flush(brief)
            await events.emit_brief_updated(self._publisher, brief, trace_id=trace_id)
            await events.emit_brief_completed(self._publisher, brief, trace_id=trace_id)
        else:
            brief.status = "in_progress"
            await self._flush(brief)
            await events.emit_brief_updated(self._publisher, brief, trace_id=trace_id)
            await self._generate_and_append_question(brief, trace_id=trace_id)

        return brief

    async def force_complete(self, brief_id: UUID, *, trace_id: str) -> Brief:
        brief = await self.get(brief_id)
        if brief.status == "complete":
            return brief
        brief.status = "complete"
        await self._flush(brief)
        await events.emit_brief_completed(self._publisher, brief, trace_id=trace_id)
        return brief

    async def abandon(self, brief_id: UUID, *, reason: str | None, trace_id: str) -> Brief:
        brief = await self.get(brief_id)
        brief.status = "abandoned"
        md = dict[str, Any](brief.metadata_ or {})
        md["abandon_reason"] = reason
        md["abandoned_at"] = datetime.now(UTC).isoformat()
        brief.metadata_ = md
        await self._flush(brief)
        await events.emit_brief_updated(self._publisher, brief, trace_id=trace_id)
        return brief

    async def reset_question(self, brief_id: UUID, *, question_index: int, trace_id: str) -> Brief:
        brief = await self.get(brief_id)
        qa = list(brief.qa_history or [])
        if question_index < 0 or question_index >= len(qa):
            raise ValidationError(f"Question index {question_index} out of range")
        item = dict[str, Any](qa[question_index])
        item["answer"] = None
        item["answered_at"] = None
        qa[question_index] = item
        brief.qa_history = qa
        brief.status = "in_progress"
        await self._flush(brief)
        await events.emit_brief_updated(self._publisher, brief, trace_id=trace_id)
        return brief

    async def archive(self, brief_id: UUID, *, trace_id: str) -> None:
        brief = await self.get(brief_id)
        brief.status = "archived"
        await self._flush(brief)
        await events.emit_brief_updated(self._publisher, brief, trace_id=trace_id)

    async def get(self, brief_id: UUID) -> Brief:
        brief = await self._repo.get(brief_id)
        if brief is None:
            raise NotFoundError(f"Brief {brief_id} not found")
        return brief

    async def list(
        self, *, tenant_id: UUID, status: str | None, limit: int, offset: int
    ) -> list[Brief]:
        return await self._repo.list(tenant_id=tenant_id, status=status, limit=limit, offset=offset)

    async def _flush(self, brief: Brief) -> None:
        """Flush and refresh to avoid expired-attribute access outside the async greenlet."""
        await self._repo.session.flush()
        await self._repo.session.refresh(brief)

    # ---- internals ----

    @staticmethod
    def _brief_data(brief: Brief) -> dict[str, Any]:
        return {
            "identity": brief.identity,
            "offering": brief.offering,
            "targeting_hints": brief.targeting_hints,
            "outreach_goals": brief.outreach_goals,
        }

    async def _re_extract(self, brief: Brief, *, trace_id: str) -> None:
        """Re-extract Brief fields, now including accumulated Q&A."""
        qa = brief.qa_history or []
        qa_text = "\n".join(
            f"В: {q['question']}\nО: {q.get('answer', '(не отвечено)')}" for q in qa
        )
        raw = brief.raw_input or {}
        prompt = build_extract_prompt(
            raw_text=raw.get("text"),
            urls=raw.get("urls", []),
            transcript=raw.get("transcript"),
            website_contents=raw.get("website_contents"),
        )
        user_with_qa = prompt.user + f"\n\n<уточнения>\n{qa_text}\n</уточнения>\n"
        extracted = await self._llm.complete_json(
            tenant_id=str(brief.tenant_id),
            task_type=prompt.task_type,
            system=prompt.system,
            user=user_with_qa,
            output_schema=ExtractSchema,
            trace_id=trace_id,
        )
        brief.identity = extracted.identity.model_dump()
        brief.offering = extracted.offering.model_dump()
        brief.targeting_hints = extracted.targeting_hints.model_dump()
        brief.outreach_goals = extracted.outreach_goals.model_dump()

    async def _generate_and_append_question(self, brief: Brief, *, trace_id: str) -> None:
        next_field = get_next_priority_field(self._brief_data(brief))
        if next_field is None:
            return

        already_asked = [q["question"] for q in (brief.qa_history or [])]
        missing = brief.missing_info or []
        prompt = build_generate_questions_prompt(
            brief_json=json.dumps(self._brief_data(brief), ensure_ascii=False, indent=2),
            missing_fields=missing,
            already_asked=already_asked,
            max_questions=self._settings.max_questions_per_iteration,
        )
        result = await self._llm.complete_json(
            tenant_id=str(brief.tenant_id),
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=QuestionsSchema,
            trace_id=trace_id,
        )

        now = datetime.now(UTC).isoformat()
        qa = list(brief.qa_history or [])
        for q in result.questions:
            qa.append(
                {
                    "question": q.question,
                    "priority": q.priority,
                    "asked_at": now,
                    "answered_at": None,
                    "generated_by": f"llm:{self._settings.llm_model}",
                    "question_template_id": None,
                }
            )
        brief.qa_history = qa
        await self._flush(brief)
        await events.emit_brief_questions_asked(
            self._publisher,
            brief,
            questions=[q.model_dump() for q in result.questions],
            trace_id=trace_id,
        )
