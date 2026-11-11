import base64
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.queue import Queue


def encode_cursor(created_at: datetime, job_id: UUID) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": str(job_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + padding).decode()
    data = json.loads(raw)
    return datetime.fromisoformat(data["c"]), UUID(data["i"])


async def get_by_id(
    session: AsyncSession,
    tenant_id: UUID,
    job_id: UUID,
    *,
    lock: bool = False,
) -> tuple[Job, str] | None:
    stmt = (
        select(Job, Queue.name)
        .join(Queue, Queue.id == Job.queue_id)
        .where(Job.tenant_id == tenant_id, Job.id == job_id)
    )
    if lock:
        stmt = stmt.with_for_update(of=Job)
    row = (await session.execute(stmt)).one_or_none()
    return (row[0], row[1]) if row else None


async def get_by_idempotency_key(
    session: AsyncSession, tenant_id: UUID, key: str
) -> Job | None:
    result = await session.execute(
        select(Job).where(Job.tenant_id == tenant_id, Job.idempotency_key == key)
    )
    return result.scalar_one_or_none()


async def list_jobs(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    statuses: list[str] | None = None,
    queue_name: str | None = None,
    task_name: str | None = None,
    priority: int | None = None,
    cursor: tuple[datetime, UUID] | None = None,
    limit: int = 50,
) -> tuple[list[tuple[Job, str]], str | None]:
    stmt = (
        select(Job, Queue.name)
        .join(Queue, Queue.id == Job.queue_id)
        .where(Job.tenant_id == tenant_id)
    )
    if statuses:
        stmt = stmt.where(Job.status.in_(statuses))
    if queue_name:
        stmt = stmt.where(Queue.name == queue_name)
    if task_name:
        stmt = stmt.where(Job.task_name == task_name)
    if priority is not None:
        stmt = stmt.where(Job.priority == priority)
    if cursor is not None:
        c_ts, c_id = cursor
        stmt = stmt.where(
            or_(
                Job.created_at < c_ts,
                and_(Job.created_at == c_ts, Job.id < c_id),
            )
        )
    stmt = stmt.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit + 1)

    rows = list((await session.execute(stmt)).all())
    next_cursor: str | None = None
    if len(rows) > limit:
        last_job = rows[limit - 1][0]
        next_cursor = encode_cursor(last_job.created_at, last_job.id)
        rows = rows[:limit]

    return [(r[0], r[1]) for r in rows], next_cursor


async def get_attempts(session: AsyncSession, job_id: UUID) -> list:
    from app.models.job_attempt import JobAttempt
    result = await session.execute(
        select(JobAttempt)
        .where(JobAttempt.job_id == job_id)
        .order_by(JobAttempt.attempt_number.desc())
    )
    return list(result.scalars().all())
