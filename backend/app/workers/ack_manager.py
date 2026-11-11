import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.policies.retry import compute_backoff
from app.workers.executor import ExecutionOutcome


async def record_success(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    attempt_id: uuid.UUID,
    worker_id: uuid.UUID,
    lease_token: uuid.UUID,
    outcome: ExecutionOutcome,
) -> bool:
    now = datetime.now(UTC)
    result_json = json.dumps(outcome.result) if outcome.result is not None else None

    updated_job = await session.execute(
        text("""
            UPDATE jobs SET
                status = 'succeeded',
                result = CAST(:result AS jsonb),
                completed_at = :now,
                locked_by = NULL,
                lease_token = NULL,
                locked_until = NULL,
                updated_at = :now
            WHERE id = :job_id
              AND status = 'running'
              AND lease_token = :lease_token
              AND locked_by = :worker_id
        """),
        {
            "result": result_json, "now": now, "job_id": job_id,
            "lease_token": lease_token, "worker_id": worker_id,
        },
    )
    if updated_job.rowcount == 0:
        await session.rollback()
        return False

    updated_attempt = await session.execute(
        text("""
            UPDATE job_attempts SET
                status = 'succeeded',
                finished_at = :now,
                duration_ms = :duration_ms
            WHERE id = :attempt_id AND status = 'running'
        """),
        {"now": now, "duration_ms": outcome.duration_ms, "attempt_id": attempt_id},
    )
    if updated_attempt.rowcount == 0:
        await session.rollback()
        return False

    await session.commit()
    return True


async def record_failure(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    attempt_id: uuid.UUID,
    worker_id: uuid.UUID,
    lease_token: uuid.UUID,
    outcome: ExecutionOutcome,
    retry_policy: dict | None,
) -> bool:
    now = datetime.now(UTC)
    attempt_status = "timed_out" if outcome.timed_out else "failed"

    # Read the current attempt count and max under lock so retry-vs-DL is
    # decided against the authoritative row.
    locked = (
        await session.execute(
            text("""
                SELECT attempts, max_attempts, tenant_id
                FROM jobs
                WHERE id = :job_id
                  AND status = 'running'
                  AND lease_token = :lease_token
                  AND locked_by = :worker_id
                FOR UPDATE
            """),
            {"job_id": job_id, "lease_token": lease_token, "worker_id": worker_id},
        )
    ).one_or_none()

    if locked is None:
        await session.rollback()
        return False

    current_attempts, max_attempts, tenant_id = locked
    will_retry = current_attempts < max_attempts and outcome.retryable

    # --- branch 1: retry_scheduled (direct assignment, no COALESCE / CASE) ---
    if will_retry:
        delay = compute_backoff(current_attempts, retry_policy)
        new_scheduled_at = now + timedelta(seconds=delay)
        upd = await session.execute(
            text("""
                UPDATE jobs SET
                    status = 'retry_scheduled',
                    scheduled_at = :new_scheduled_at,
                    last_error = :last_error,
                    locked_by = NULL,
                    lease_token = NULL,
                    locked_until = NULL,
                    updated_at = :now
                WHERE id = :job_id
            """),
            {
                "new_scheduled_at": new_scheduled_at,
                "last_error": (outcome.error_message or "")[:8000],
                "now": now,
                "job_id": job_id,
            },
        )
        if upd.rowcount == 0:
            await session.rollback()
            return False

    # --- branch 2: dead_lettered (direct assignment) ---
    else:
        upd = await session.execute(
            text("""
                UPDATE jobs SET
                    status = 'dead_lettered',
                    last_error = :last_error,
                    completed_at = :now,
                    locked_by = NULL,
                    lease_token = NULL,
                    locked_until = NULL,
                    updated_at = :now
                WHERE id = :job_id
            """),
            {
                "last_error": (outcome.error_message or "")[:8000],
                "now": now,
                "job_id": job_id,
            },
        )
        if upd.rowcount == 0:
            await session.rollback()
            return False

    # --- attempt record ---
    upd_attempt = await session.execute(
        text("""
            UPDATE job_attempts SET
                status = :status,
                finished_at = :now,
                duration_ms = :duration_ms,
                error_type = :error_type,
                error_message = :error_message,
                error_traceback = :error_traceback
            WHERE id = :attempt_id AND status = 'running'
        """),
        {
            "status": attempt_status,
            "now": now,
            "duration_ms": outcome.duration_ms,
            "error_type": outcome.error_type,
            "error_message": (outcome.error_message or "")[:4000] or None,
            "error_traceback": outcome.error_traceback,
            "attempt_id": attempt_id,
        },
    )
    if upd_attempt.rowcount == 0:
        await session.rollback()
        return False

    # --- DL entry only when we're actually dead-lettering ---
    if not will_retry:
        await session.execute(
            text("""
                INSERT INTO dead_letter_entries (
                    id, job_id, tenant_id, failure_reason, final_error_type
                ) VALUES (
                    :id, :job_id, :tenant_id, :reason, :error_type
                )
                ON CONFLICT (job_id) DO NOTHING
            """),
            {
                "id": uuid.uuid4(),
                "job_id": job_id,
                "tenant_id": tenant_id,
                "reason": (outcome.error_message or "")[:8000] or None,
                "error_type": outcome.error_type,
            },
        )

    await session.commit()
    return True
