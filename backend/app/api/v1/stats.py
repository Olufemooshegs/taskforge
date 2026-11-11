from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_tenant
from app.db.session import get_session
from app.schemas.stats import (
    JobCounts,
    OverviewStats,
    QueueStat,
    RecentFailure,
    WorkerCounts,
)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=OverviewStats)
async def get_overview(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(require_tenant),
) -> OverviewStats:
    status_rows = (
        await session.execute(
            text(
                "SELECT status, COUNT(*) FROM jobs "
                "WHERE tenant_id = :tid GROUP BY status"
            ),
            {"tid": tenant_id},
        )
    ).all()
    counts = {row[0]: row[1] for row in status_rows}
    jobs = JobCounts(
        total=sum(counts.values()),
        queued=counts.get("queued", 0),
        running=counts.get("running", 0),
        scheduled=counts.get("scheduled", 0),
        retry_scheduled=counts.get("retry_scheduled", 0),
        succeeded=counts.get("succeeded", 0),
        failed=counts.get("failed", 0),
        dead_lettered=counts.get("dead_lettered", 0),
        cancelled=counts.get("cancelled", 0),
    )

    w = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS total, "
                "COUNT(*) FILTER (WHERE status='active') AS active, "
                "COUNT(*) FILTER (WHERE last_heartbeat_at > now() - interval '60 seconds') AS live "
                "FROM workers WHERE tenant_id = :tid"
            ),
            {"tid": tenant_id},
        )
    ).one()
    workers = WorkerCounts(total=w.total, active=w.active, live=w.live)

    queue_rows = (
        await session.execute(
            text(
                """
                SELECT q.id, q.name, q.is_active, q.max_concurrency,
                       COUNT(j.id) FILTER (WHERE j.status='queued') AS queued,
                       COUNT(j.id) FILTER (WHERE j.status='running') AS running,
                       COUNT(j.id) FILTER (WHERE j.status='retry_scheduled') AS retry_scheduled
                FROM queues q
                LEFT JOIN jobs j ON j.queue_id = q.id
                WHERE q.tenant_id = :tid
                GROUP BY q.id, q.name, q.is_active, q.max_concurrency
                ORDER BY q.name
                """
            ),
            {"tid": tenant_id},
        )
    ).all()
    queues = [
        QueueStat(
            id=r.id, name=r.name, is_active=r.is_active,
            max_concurrency=r.max_concurrency,
            queued=r.queued, running=r.running, retry_scheduled=r.retry_scheduled,
        )
        for r in queue_rows
    ]

    failure_rows = (
        await session.execute(
            text(
                """
                SELECT id, task_name, status, last_error, updated_at
                FROM jobs
                WHERE tenant_id = :tid
                  AND status IN ('failed', 'dead_lettered')
                ORDER BY updated_at DESC
                LIMIT 10
                """
            ),
            {"tid": tenant_id},
        )
    ).all()
    recent = [
        RecentFailure(
            id=r.id, task_name=r.task_name, status=r.status,
            last_error=r.last_error, updated_at=r.updated_at,
        )
        for r in failure_rows
    ]

    return OverviewStats(jobs=jobs, workers=workers, queues=queues, recent_failures=recent)
