from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_tenant
from app.db.session import get_session
from app.schemas.dead_letter import DeadLetterDetail, DeadLetterListResponse
from app.services import dead_letter_service

router = APIRouter(prefix="/dead-letters", tags=["dead-letters"])


@router.get("", response_model=DeadLetterListResponse)
async def list_dead_letters(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> DeadLetterListResponse:
    return await dead_letter_service.list_dead_letters(
        session, tenant_id, cursor_str=cursor, limit=limit
    )


@router.get("/{dl_id}", response_model=DeadLetterDetail)
async def get_dead_letter(
    dl_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
) -> DeadLetterDetail:
    return await dead_letter_service.get_dead_letter(session, tenant_id, dl_id)
