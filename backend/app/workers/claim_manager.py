import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_attempt import JobAttempt


@dataclass
class ClaimedJob:
    job_id: uuid.UUID
    attempt_id: uuid.UUID
    attempt_number: int
    queue_id: uuid.UUID
    task_name: str
    payload: dict[str, Any]
    retry_policy: dict[str, Any] | None
    timeout_seconds: int
    lease_token: uuid.UUID
    lease_generation: int


CLAIM_SQL = text("""
    WITH candidate AS (
        SELECT id FROM jobs
        WHERE queue_id = ANY(:queue_ids)
          AND status = 'queued'
          AND scheduled_at <= now()
        ORDER BY priority DESC, scheduled_at ASC, created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE jobs SET
        status = 'running',
        locked_by = :worker_id,
        lease_token = :lease_token,
        lease_generation = lease_generation + 1,
        locked_until = now() + make_interval(secs => :lease_seconds),
        attempts = attempts + 1,
        started_at = COALESCE(started_at, now()),
        updated_at = now()
    WHERE id IN (SELECT id FROM candidate)
    RETURNING id, queue_id, task_name, payload, attempts,
              retry_policy, timeout_seconds, lease_generation
""")


async def claim_one(
    session: AsyncSession,
    *,
    worker_id: uuid.UUID,
    queue_ids: list[uuid.UUID],
    lease_duration_seconds: int = 60,
) -> ClaimedJob | None:
    if not queue_ids:
        return None

    lease_token = uuid.uuid4()
    row = (
        await session.execute(
            CLAIM_SQL,
            {
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_seconds": lease_duration_seconds,
                "queue_ids": queue_ids,
            },
        )
    ).one_or_none()

    if row is None:
        await session.rollback()
        return None

    (
        job_id, queue_id, task_name, payload,
        attempts, retry_policy, timeout_seconds, lease_generation,
    ) = row

    attempt_id = uuid.uuid4()
    session.add(
        JobAttempt(
            id=attempt_id,
            job_id=job_id,
            worker_id=worker_id,
            attempt_number=attempts,
            status="running",
            started_at=datetime.now(UTC),
        )
    )
    await session.commit()

    return ClaimedJob(
        job_id=job_id,
        attempt_id=attempt_id,
        attempt_number=attempts,
        queue_id=queue_id,
        task_name=task_name,
        payload=payload,
        retry_policy=retry_policy,
        timeout_seconds=timeout_seconds,
        lease_token=lease_token,
        lease_generation=lease_generation,
    )
