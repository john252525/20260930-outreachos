"""HTTP routes for llm-gateway."""

from fastapi import APIRouter, Depends

from llm_gateway.api.deps import get_service
from llm_gateway.schemas import CompleteRequest, CompleteResponse
from llm_gateway.service import LLMGatewayService

router = APIRouter(prefix="/v1", tags=["llm"])


@router.post("/complete", response_model=CompleteResponse)
async def complete(
    req: CompleteRequest,
    svc: LLMGatewayService = Depends(get_service),
) -> CompleteResponse:
    return await svc.complete(req)
