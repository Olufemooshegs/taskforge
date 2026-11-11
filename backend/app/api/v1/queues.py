from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_tenant
from app.db.session import get_session
from app.repositories import queue_repository
from app.schemas.job import QueueListResponse, QueueResponse

router = APIRouter(prefix="/queues", tags=["queues"])


@router.get("", response_model=QueueListResponse)
async def list_queues(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
) -> QueueListResponse:
    queues = await queue_repository.list_for_tenant(session, tenant_id)
    return QueueListResponse(items=[QueueResponse.model_validate(q) for q in queues])
