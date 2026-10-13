"""Business logic for ml-scoring."""

from uuid import UUID

import structlog

from db.types import generate_uuid7
from ml_scoring.config import Settings
from ml_scoring.features.scorer import BaselineScorer
from ml_scoring.models import ContactFeatures
from ml_scoring.repository import FeatureRepository
from ml_scoring.schemas import FeaturesUpsert, ScoreResponse

logger = structlog.get_logger()


class ScoringService:
    def __init__(self, *, repo: FeatureRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings
        self._scorer = BaselineScorer()

    async def score(self, *, tenant_id: UUID, contact_id: UUID) -> ScoreResponse:
        features = await self._repo.get_features(tenant_id, contact_id)
        data: dict[str, object] = {}
        if features is not None:
            data = {
                "role_category": features.role_category,
                "seniority": features.seniority,
                "company_industry": features.company_industry,
                "company_employee_count": features.company_employee_count,
                "company_signals_count": features.company_signals_count,
            }
        breakdown = self._scorer.score(data)
        return ScoreResponse(
            contact_id=contact_id,
            score=breakdown.score,
            components=breakdown.components,
            model_version=breakdown.model_version,
        )

    async def upsert_features(self, *, tenant_id: UUID, data: FeaturesUpsert) -> ContactFeatures:
        features = ContactFeatures(
            id=generate_uuid7(),
            tenant_id=tenant_id,
            contact_id=data.contact_id,
            role_category=data.role_category,
            seniority=data.seniority,
            company_industry=data.company_industry,
            company_size_range=data.company_size_range,
            company_country=data.company_country,
            company_employee_count=data.company_employee_count,
            company_signals_count=data.company_signals_count,
            days_since_company_created=data.days_since_company_created,
            has_reply=data.has_reply,
            has_positive_reply=data.has_positive_reply,
            messages_sent=data.messages_sent,
            last_message_sent_at=data.last_message_sent_at,
        )
        result = await self._repo.upsert(features)
        await self._repo.session.refresh(result)
        return result

    async def labelled_count(self, tenant_id: UUID) -> int:
        return await self._repo.count_labelled(tenant_id)
