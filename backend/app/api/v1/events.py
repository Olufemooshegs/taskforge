from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_tenant
from app.db.session import get_session
from app.schemas.events import Event, EventsResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/recent", response_model=EventsResponse)
async def recent_events(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
    limit: int = Query(default=20, ge=1, le=100),
) -> EventsResponse:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                    a.id, a.status, a.started_at, a.finished_at,
                    a.attempt_number, a.error_type,
                    j.id AS job_id, j.task_name,
                    w.hostname AS worker_hostname
                FROM job_attempts a
                JOIN jobs j ON j.id = a.job_id
                LEFT JOIN workers w ON w.id = a.worker_id
                WHERE j.tenant_id = :tid
                ORDER BY GREATEST(a.started_at, COALESCE(a.finished_at, a.started_at)) DESC
                LIMIT :lim
                """
            ),
            {"tid": tenant_id, "lim": limit},
        )
    ).all()

    items: list[Event] = []
    for r in rows:
        if r.status == "running":
            items.append(Event(
                id=str(r.id), kind="claimed", job_id=str(r.job_id),
                task_name=r.task_name, attempt_number=r.attempt_number,
                at=r.started_at, worker_hostname=r.worker_hostname,
            ))
        elif r.status == "succeeded":
            items.append(Event(
                id=str(r.id), kind="succeeded", job_id=str(r.job_id),
                task_name=r.task_name, attempt_number=r.attempt_number,
                at=r.finished_at or r.started_at, worker_hostname=r.worker_hostname,
            ))
        elif r.status == "failed":
            items.append(Event(
                id=str(r.id), kind="failed", job_id=str(r.job_id),
                task_name=r.task_name, attempt_number=r.attempt_number,
                at=r.finished_at or r.started_at, detail=r.error_type,
                worker_hostname=r.worker_hostname,
            ))
        elif r.status == "timed_out":
            items.append(Event(
                id=str(r.id), kind="timed_out", job_id=str(r.job_id),
                task_name=r.task_name, attempt_number=r.attempt_number,
                at=r.finished_at or r.started_at, worker_hostname=r.worker_hostname,
            ))
        elif r.status == "worker_lost":
            items.append(Event(
                id=str(r.id), kind="worker_lost", job_id=str(r.job_id),
                task_name=r.task_name, attempt_number=r.attempt_number,
                at=r.finished_at or r.started_at, worker_hostname=r.worker_hostname,
            ))

    return EventsResponse(items=items)
