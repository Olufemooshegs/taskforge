"""Lease reaper.

Scans for `running` jobs whose `locked_until` has passed. For each:

  1. Closes any still-open `job_attempts` row as `worker_lost`.
  2. Clears lease fields on the job.
  3. If retries remain: sets `retry_scheduled` with exponential backoff.
     Otherwise: sets `dead_lettered` + creates a `dead_letter_entries` row.
  4. Writes an audit_log row.

All steps in one transaction per job (short lock hold).

Worker crash is considered retryable (spec §9). If the handler would also
fail permanently, the retry attempt will discover that and dead-letter on
its own — the reaper doesn't try to predict handler behavior.
"""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db.session import SessionFactory
from app.domain.policies.retry import compute_backoff

log = logging.getLogger("taskforge.recovery")

BATCH_SIZE = 50


async def _recover_one(session, job_id: uuid.UUID) -> bool:
    now = datetime.now(UTC)

    # Lock the job row (only if it's still expired + running)
    row = (
        await session.execute(
            text("""
                SELECT id, attempts, max_attempts, retry_policy, tenant_id,
                       locked_until
                FROM jobs
                WHERE id = :job_id
                  AND status = 'running'
                  AND locked_until < now()
                FOR UPDATE
            """),
            {"job_id": job_id},
        )
    ).one_or_none()

    if row is None:
        await session.rollback()
        return False

    (
        job_id, attempts, max_attempts, retry_policy, tenant_id, _locked_until,
    ) = row

    # Close the in-flight attempt as worker_lost (only if still running)
    open_attempt = (
        await session.execute(
            text("""
                SELECT id, started_at
                FROM job_attempts
                WHERE job_id = :job_id AND status = 'running'
                ORDER BY attempt_number DESC
                LIMIT 1
                FOR UPDATE
            """),
            {"job_id": job_id},
        )
    ).one_or_none()

    if open_attempt is not None:
        attempt_id, started_at = open_attempt
        dur_ms = (
            int((now - started_at).total_seconds() * 1000)
            if started_at is not None
            else None
        )
        await session.execute(
            text("""
                UPDATE job_attempts SET
                    status = 'worker_lost',
                    finished_at = :now,
                    duration_ms = :dur,
                    error_type = 'worker_lost',
                    error_message = 'lease expired — worker presumed dead'
                WHERE id = :aid AND status = 'running'
            """),
            {"now": now, "dur": dur_ms, "aid": attempt_id},
        )

    # Retry vs dead-letter
    will_retry = attempts < max_attempts
    if will_retry:
        delay = compute_backoff(attempts, retry_policy)
        new_scheduled_at = now + timedelta(seconds=delay)
        await session.execute(
            text("""
                UPDATE jobs SET
                    status = 'retry_scheduled',
                    scheduled_at = :new_sched,
                    last_error = 'lease expired — worker presumed dead',
                    locked_by = NULL,
                    lease_token = NULL,
                    locked_until = NULL,
                    updated_at = :now
                WHERE id = :job_id
            """),
            {
                "new_sched": new_scheduled_at,
                "now": now,
                "job_id": job_id,
            },
        )
    else:
        await session.execute(
            text("""
                UPDATE jobs SET
                    status = 'dead_lettered',
                    last_error = 'lease expired — worker presumed dead',
                    completed_at = :now,
                    locked_by = NULL,
                    lease_token = NULL,
                    locked_until = NULL,
                    updated_at = :now
                WHERE id = :job_id
            """),
            {"now": now, "job_id": job_id},
        )
        await session.execute(
            text("""
                INSERT INTO dead_letter_entries
                    (id, job_id, tenant_id, failure_reason, final_error_type)
                VALUES (:id, :jid, :tid, :reason, 'worker_lost')
                ON CONFLICT (job_id) DO NOTHING
            """),
            {
                "id": uuid.uuid4(),
                "jid": job_id,
                "tid": tenant_id,
                "reason": "lease expired — worker presumed dead",
            },
        )

    # Audit
    await session.execute(
        text("""
            INSERT INTO audit_logs
                (id, tenant_id, actor, action, resource_type, resource_id, extra_data)
            VALUES (:id, :tid, 'system:recovery', 'worker_lost',
                    'job', :jid, CAST(:meta AS jsonb))
        """),
        {
            "id": uuid.uuid4(),
            "tid": tenant_id,
            "jid": job_id,
            "meta": json.dumps({
                "old_status": "running",
                "new_status": "retry_scheduled" if will_retry else "dead_lettered",
                "attempts": attempts,
                "max_attempts": max_attempts,
            }),
        },
    )

    await session.commit()
    return True


async def run_one_cycle(queue_ids: list[uuid.UUID]) -> int:
    """Scan for expired leases, recover up to BATCH_SIZE."""
    if not queue_ids:
        return 0

    async with SessionFactory() as session:
        candidate_rows = (
            await session.execute(
                text("""
                    SELECT id FROM jobs
                    WHERE status = 'running'
                      AND locked_until < now()
                      AND queue_id = ANY(:qids)
                    LIMIT :lim
                """),
                {"qids": queue_ids, "lim": BATCH_SIZE},
            )
        ).all()
        await session.commit()

    recovered = 0
    for (job_id,) in candidate_rows:
        try:
            async with SessionFactory() as session:
                if await _recover_one(session, job_id):
                    recovered += 1
                    log.warning("recovered expired lease for job %s", job_id)
        except Exception:
            log.exception("recovery failed for job %s", job_id)
    return recovered


async def recovery_loop(
    stop_event,
    queue_ids: list[uuid.UUID],
    scan_interval_seconds: int,
) -> None:
    import asyncio

    log.info("recovery loop started (interval=%ds)", scan_interval_seconds)
    while not stop_event.is_set():
        try:
            n = await run_one_cycle(queue_ids)
            if n:
                log.warning("recovery: %d expired lease(s) recovered", n)
        except Exception:
            log.exception("recovery cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=scan_interval_seconds)
        except asyncio.TimeoutError:
            pass
