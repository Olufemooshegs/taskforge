from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_tenant
from app.db.session import get_session
from app.schemas.job import (
    JobDetail,
    JobListResponse,
    JobSubmitRequest,
    JobSubmitResponse,
)
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobSubmitResponse,
)
async def submit_job(
    payload: JobSubmitRequest,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
) -> JobSubmitResponse:
    response, _ = await job_service.submit_job(session, tenant_id, payload)
    return response


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
) -> JobDetail:
    return await job_service.get_job(session, tenant_id, job_id)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
    status: list[str] | None = Query(default=None),
    queue: str | None = Query(default=None),
    task_name: str | None = Query(default=None),
    priority: int | None = Query(default=None, ge=1, le=3),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> JobListResponse:
    return await job_service.list_jobs(
        session,
        tenant_id,
        statuses=status,
        queue_name=queue,
        task_name=task_name,
        priority=priority,
        cursor_str=cursor,
        limit=limit,
    )


@router.post("/{job_id}/cancel", response_model=JobDetail)
async def cancel_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
) -> JobDetail:
    return await job_service.cancel_job(session, tenant_id, job_id)
