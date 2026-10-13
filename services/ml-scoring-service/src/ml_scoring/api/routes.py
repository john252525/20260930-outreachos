"""HTTP routes for ml-scoring."""

from uuid import UUID

from fastapi import APIRouter, Depends

from common.context import get_tenant_id
from common.errors import ValidationError
from ml_scoring.api.deps import get_service
from ml_scoring.schemas import FeaturesRead, FeaturesUpsert, ScoreRequest, ScoreResponse
from ml_scoring.service import ScoringService

router = APIRouter(tags=["scoring"])


def _tenant() -> UUID:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    return tenant_id


@router.post("/score", response_model=ScoreResponse)
async def score(data: ScoreRequest, svc: ScoringService = Depends(get_service)) -> ScoreResponse:
    return await svc.score(tenant_id=_tenant(), contact_id=data.contact_id)


@router.post("/features", response_model=FeaturesRead)
async def upsert_features(
    data: FeaturesUpsert, svc: ScoringService = Depends(get_service)
) -> FeaturesRead:
    features = await svc.upsert_features(tenant_id=_tenant(), data=data)
    return FeaturesRead.model_validate(features)


@router.get("/stats")
async def stats(svc: ScoringService = Depends(get_service)) -> dict[str, int]:
    return {"labelled_contacts": await svc.labelled_count(_tenant())}
