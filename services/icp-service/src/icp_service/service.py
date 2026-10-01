"""Business logic for icp-service."""

import json
from typing import Any
from uuid import UUID

import structlog
from uuid6 import uuid7

from common.errors import AppError, NotFoundError, ValidationError
from icp_service import events
from icp_service.brief_client import BriefClient, BriefNotFoundError
from icp_service.config import Settings
from icp_service.llm.client import LLMClient
from icp_service.llm.prompts.generate_icp import build_generate_icp_prompt
from icp_service.llm.schemas import ICPGenerated
from icp_service.models import ICP
from icp_service.repository import ICPRepository
from icp_service.weight_normalizer import normalize_weights
from nats_client.publisher import Publisher

logger = structlog.get_logger()


class ICPService:
    def __init__(
        self,
        repo: ICPRepository,
        brief_client: BriefClient,
        llm: LLMClient,
        publisher: Publisher,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._brief = brief_client
        self._llm = llm
        self._publisher = publisher
        self._settings = settings

    async def _flush(self, icp: ICP) -> None:
        # Flush + refresh to avoid expired-attribute access outside the async greenlet.
        await self._repo.session.flush()
        await self._repo.session.refresh(icp)

    async def generate(self, *, tenant_id: UUID, brief_id: str, trace_id: str) -> ICP:
        try:
            brief = await self._brief.get_brief(
                brief_id, tenant_id=str(tenant_id), trace_id=trace_id
            )
        except BriefNotFoundError as e:
            raise NotFoundError(f"Brief {brief_id} not found") from e

        if brief.get("status") == "archived":
            raise ValidationError("Cannot generate ICP for archived brief")

        brief_json = json.dumps(
            {
                "identity": brief.get("identity", {}),
                "offering": brief.get("offering", {}),
                "targeting_hints": brief.get("targeting_hints", {}),
                "outreach_goals": brief.get("outreach_goals", {}),
                "completeness_score": brief.get("completeness_score", 0.0),
            },
            ensure_ascii=False,
            indent=2,
        )

        prompt = build_generate_icp_prompt(
            brief_json=brief_json,
            min_segments=self._settings.min_segments,
            max_segments=self._settings.max_segments,
        )
        generated = await self._llm.complete_json(
            tenant_id=str(tenant_id),
            task_type=prompt.task_type,
            system=prompt.system,
            user=prompt.user,
            output_schema=ICPGenerated,
            trace_id=trace_id,
        )

        warnings_all: list[str] = []
        segments: list[dict[str, Any]] = []
        for seg in generated.segments:
            weights = seg.scoring_weights.model_dump()
            normalized, warnings = normalize_weights(weights)
            warnings_all.extend([f"segment[{seg.name}]: {w}" for w in warnings])
            seg_dict = seg.model_dump()
            seg_dict["id"] = str(uuid7())
            seg_dict["scoring_weights"] = normalized
            segments.append(seg_dict)

        if warnings_all:
            logger.warning(
                "icp_weight_normalization_warnings", warnings=warnings_all, brief_id=brief_id
            )

        if not segments:
            raise AppError("LLM generated no segments", code="icp_empty", status_code=502)

        segments = segments[: self._settings.max_segments]

        payload = {
            "anti_icp": generated.anti_icp.model_dump(),
            "segments": segments,
            "generated_by": f"llm:{self._settings.llm_model}",
            "llm_confidence": generated.llm_confidence,
        }

        max_version = await self._repo.get_max_version(tenant_id, brief_id)
        new_version = max_version + 1
        await self._repo.deactivate_all(tenant_id, brief_id)

        icp = ICP(
            tenant_id=tenant_id,
            brief_id=brief_id,
            version=new_version,
            is_active=True,
            payload=payload,
            segments_count=len(segments),
            llm_confidence=generated.llm_confidence,
        )
        await self._repo.add(icp)
        await self._flush(icp)

        if generated.llm_confidence < self._settings.min_confidence:
            md = dict(icp.metadata_ or {})
            md["needs_review"] = True
            md["reason"] = (
                f"llm_confidence {generated.llm_confidence} < {self._settings.min_confidence}"
            )
            icp.metadata_ = md
            await self._flush(icp)

        if new_version == 1:
            await events.emit_icp_generated(self._publisher, icp, trace_id=trace_id)
        else:
            await events.emit_icp_revised(self._publisher, icp, trace_id=trace_id)

        logger.info(
            "icp_generated",
            icp_id=str(icp.id),
            brief_id=brief_id,
            version=new_version,
            segments=len(segments),
            llm_confidence=generated.llm_confidence,
            reasoning=generated.reasoning[:200],
        )
        return icp

    async def revise(self, *, tenant_id: UUID, icp_id: UUID, trace_id: str) -> ICP:
        icp = await self.get(icp_id)
        return await self.generate(tenant_id=tenant_id, brief_id=icp.brief_id, trace_id=trace_id)

    async def activate(self, *, tenant_id: UUID, icp_id: UUID, trace_id: str) -> ICP:
        icp = await self.get(icp_id)
        if icp.is_active:
            return icp
        await self._repo.deactivate_all(tenant_id, icp.brief_id)
        icp.is_active = True
        await self._flush(icp)
        await events.emit_icp_revised(self._publisher, icp, trace_id=trace_id)
        return icp

    async def deactivate(self, *, tenant_id: UUID, icp_id: UUID, trace_id: str) -> ICP:
        icp = await self.get(icp_id)
        if not icp.is_active:
            return icp
        icp.is_active = False
        await self._flush(icp)
        await events.emit_icp_revised(self._publisher, icp, trace_id=trace_id)
        return icp

    async def get(self, icp_id: UUID) -> ICP:
        icp = await self._repo.get(icp_id)
        if icp is None:
            raise NotFoundError(f"ICP {icp_id} not found")
        return icp

    async def list_by_brief(self, *, tenant_id: UUID, brief_id: str) -> list[ICP]:
        return await self._repo.list_by_brief(tenant_id, brief_id)

    async def get_active(self, *, tenant_id: UUID, brief_id: str) -> ICP | None:
        return await self._repo.get_active(tenant_id, brief_id)

    async def list(self, *, tenant_id: UUID, limit: int, offset: int) -> list[ICP]:
        return await self._repo.list(tenant_id=tenant_id, limit=limit, offset=offset)
