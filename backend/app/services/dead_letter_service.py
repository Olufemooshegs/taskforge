from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.dead_letter import DeadLetterEntry
from app.models.job import Job
from app.repositories.job_repository import decode_cursor, encode_cursor
from app.schemas.dead_letter import (
    DeadLetterDetail,
    DeadLetterListResponse,
    DeadLetterSummary,
)


async def list_dead_letters(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    cursor_str: str | None = None,
    limit: int = 50,
) -> DeadLetterListResponse:
    stmt = select(DeadLetterEntry).where(DeadLetterEntry.tenant_id == tenant_id)
    if cursor_str:
        c_ts, c_id = decode_cursor(cursor_str)
        stmt = stmt.where(
            or_(
                DeadLetterEntry.dead_lettered_at < c_ts,
                and_(
                    DeadLetterEntry.dead_lettered_at == c_ts,
                    DeadLetterEntry.id < c_id,
                ),
            )
        )
    stmt = stmt.order_by(
        DeadLetterEntry.dead_lettered_at.desc(), DeadLetterEntry.id.desc()
    ).limit(limit + 1)

    rows = list((await session.execute(stmt)).scalars().all())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(last.dead_lettered_at, last.id)
        rows = rows[:limit]

    return DeadLetterListResponse(
        items=[DeadLetterSummary.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )


async def get_dead_letter(
    session: AsyncSession, tenant_id: UUID, dl_id: UUID
) -> DeadLetterDetail:
    row = (
        await session.execute(
            select(DeadLetterEntry, Job)
            .join(Job, Job.id == DeadLetterEntry.job_id)
            .where(
                DeadLetterEntry.tenant_id == tenant_id,
                DeadLetterEntry.id == dl_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError(f"Dead letter {dl_id} not found")
    dl, job = row
    return DeadLetterDetail(
        id=dl.id,
        job_id=dl.job_id,
        failure_reason=dl.failure_reason,
        final_error_type=dl.final_error_type,
        dead_lettered_at=dl.dead_lettered_at,
        replay_count=dl.replay_count,
        resolved_at=dl.resolved_at,
        job={
            "id": str(job.id),
            "task_name": job.task_name,
            "payload": job.payload,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "last_error": job.last_error,
            "created_at": job.created_at.isoformat(),
        },
    )
