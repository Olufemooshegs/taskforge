"""Per-job lease renewal.

While a worker is executing a handler, it must periodically extend
`jobs.locked_until` so the lease reaper doesn't conclude the worker died.
Renewal is conditional on (lease_token, locked_by, status='running'); if
any of those changed, the worker lost ownership and must NOT write a result.
"""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("taskforge.lease")


async def renew_lease(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    worker_id: uuid.UUID,
    lease_token: uuid.UUID,
    lease_duration_seconds: int,
) -> bool:
    result = await session.execute(
        text("""
            UPDATE jobs SET
                locked_until = now() + make_interval(secs => :lease),
                updated_at = now()
            WHERE id = :job_id
              AND status = 'running'
              AND lease_token = :token
              AND locked_by = :worker
        """),
        {
            "lease": lease_duration_seconds,
            "job_id": job_id,
            "token": lease_token,
            "worker": worker_id,
        },
    )
    await session.commit()
    return result.rowcount > 0
