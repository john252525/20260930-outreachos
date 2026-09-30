"""Stop-list routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from common.context import get_tenant_id
from common.errors import ValidationError
from contact_store.api.deps import get_stoplist
from contact_store.schemas import StopListEntryCreate, StopListEntryRead
from contact_store.stoplist import StopList

router = APIRouter(prefix="/stoplist", tags=["stoplist"])


@router.post("", response_model=StopListEntryRead, status_code=status.HTTP_201_CREATED)
async def add_entry(
    data: StopListEntryCreate,
    request: Request,
    sl: StopList = Depends(get_stoplist),
) -> StopListEntryRead:
    tenant_id = get_tenant_id()
    if tenant_id is None:
        raise ValidationError("X-Tenant-ID required")
    entry = await sl.add(
        tenant_id=tenant_id,
        kind=data.kind,
        value=data.value,
        reason=data.reason,
        note=data.note,
        created_by=request.headers.get("X-User-Id", "anonymous"),
    )
    return StopListEntryRead.model_validate(entry)


@router.get("", response_model=list[StopListEntryRead])
async def list_entries(
    kind: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sl: StopList = Depends(get_stoplist),
) -> list[StopListEntryRead]:
    entries = await sl.list(kind=kind, limit=limit, offset=offset)
    return [StopListEntryRead.model_validate(e) for e in entries]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_entry(
    entry_id: UUID,
    sl: StopList = Depends(get_stoplist),
) -> None:
    await sl.remove(entry_id)
