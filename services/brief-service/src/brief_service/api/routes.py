"""HTTP routes for brief-service."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from brief_service.api.deps import get_publisher, get_service
from brief_service.schemas import (
    AbandonSubmit,
    AnswerSubmit,
    BriefRead,
    BriefSummary,
    RawInputSubmit,
    ResetQuestionSubmit,
)
from brief_service.service import BriefService
from common.context import get_tenant_id, get_trace_id
from common.errors import ValidationError
from nats_client.publisher import Publisher

router = APIRouter(prefix="/briefs", tags=["briefs"])


@router.post("", response_model=BriefRead, status_code=status.HTTP_201_CREATED)
async def create_brief(
    data: RawInputSubmit,
    request: Request,
    svc: BriefService = Depends(get_service),
    publisher: Publisher = Depends(get_publisher),
) -> BriefRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    brief = await svc.create_from_raw_input(
        tenant_id=tenant_id,
        text=data.text,
        urls=[str(u) for u in data.urls],
        transcript=data.transcript,
        created_by=request.headers.get("X-User-Id", "anonymous"),
        trace_id=get_trace_id() or "",
    )
    return BriefRead.model_validate(brief)


@router.get("", response_model=list[BriefSummary])
async def list_briefs(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: BriefService = Depends(get_service),
) -> list[BriefSummary]:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    briefs = await svc.list(tenant_id=tenant_id, status=status_filter, limit=limit, offset=offset)
    return [
        BriefSummary(
            id=b.id,
            status=b.status,
            completeness_score=b.completeness_score,
            project_name=(b.identity or {}).get("project_name"),
            created_at=b.created_at,
            updated_at=b.updated_at,
        )
        for b in briefs
    ]


@router.get("/{brief_id}", response_model=BriefRead)
async def get_brief(
    brief_id: UUID,
    svc: BriefService = Depends(get_service),
) -> BriefRead:
    brief = await svc.get(brief_id)
    return BriefRead.model_validate(brief)


@router.post("/{brief_id}/answers", response_model=BriefRead)
async def answer_question(
    brief_id: UUID,
    data: AnswerSubmit,
    svc: BriefService = Depends(get_service),
) -> BriefRead:
    brief = await svc.answer_question(
        brief_id=brief_id,
        question_index=data.question_index,
        answer=data.answer,
        trace_id=get_trace_id() or "",
    )
    return BriefRead.model_validate(brief)


@router.post("/{brief_id}/complete", response_model=BriefRead)
async def force_complete(
    brief_id: UUID,
    svc: BriefService = Depends(get_service),
) -> BriefRead:
    brief = await svc.force_complete(brief_id, trace_id=get_trace_id() or "")
    return BriefRead.model_validate(brief)


@router.post("/{brief_id}/abandon", response_model=BriefRead)
async def abandon_brief(
    brief_id: UUID,
    data: AbandonSubmit,
    svc: BriefService = Depends(get_service),
) -> BriefRead:
    brief = await svc.abandon(brief_id, reason=data.reason, trace_id=get_trace_id() or "")
    return BriefRead.model_validate(brief)


@router.post("/{brief_id}/reset-question", response_model=BriefRead)
async def reset_question(
    brief_id: UUID,
    data: ResetQuestionSubmit,
    svc: BriefService = Depends(get_service),
) -> BriefRead:
    brief = await svc.reset_question(
        brief_id, question_index=data.question_index, trace_id=get_trace_id() or ""
    )
    return BriefRead.model_validate(brief)


@router.delete("/{brief_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_brief(
    brief_id: UUID,
    svc: BriefService = Depends(get_service),
) -> None:
    await svc.archive(brief_id, trace_id=get_trace_id() or "")
