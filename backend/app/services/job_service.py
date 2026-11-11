import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    IdempotencyConflictError,
    InvalidTransitionError,
    JobNotFoundError,
    PayloadTooLargeError,
    QueueNotFoundError,
)
from app.domain.enums import JobStatus
from app.domain.policies.idempotency import fingerprint_request
from app.models.job import Job
from app.repositories import job_repository, outbox_repository, queue_repository
from app.schemas.job import (
    PRIORITY_MAP,
    JobDetail,
    JobListResponse,
    JobSubmitRequest,
    JobSubmitResponse,
    JobSummary,
)

MAX_PAYLOAD_BYTES = 256 * 1024


def _submit_response(job: Job, queue_name: str) -> JobSubmitResponse:
    return JobSubmitResponse(
        job_id=job.id,
        status=job.status,
        queue=queue_name,
        task_name=job.task_name,
        created_at=job.created_at,
    )


def _job_to_detail(job: Job, queue_name: str) -> JobDetail:
    return JobDetail(
        id=job.id,
        tenant_id=job.tenant_id,
        queue_id=job.queue_id,
        queue=queue_name,
        task_name=job.task_name,
        payload=job.payload,
        result=job.result,
        status=job.status,
        priority=job.priority,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        scheduled_at=job.scheduled_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        last_error=job.last_error,
        timeout_seconds=job.timeout_seconds,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _job_to_summary(job: Job, queue_name: str) -> JobSummary:
    return JobSummary(
        id=job.id,
        queue=queue_name,
        task_name=job.task_name,
        status=job.status,
        priority=job.priority,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        scheduled_at=job.scheduled_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def submit_job(
    session: AsyncSession, tenant_id: UUID, req: JobSubmitRequest
) -> tuple[JobSubmitResponse, bool]:
    # 1. Payload size cap (before any DB work)
    size = len(
        json.dumps(req.payload, separators=(",", ":")).encode("utf-8")
    )
    if size > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(
            f"payload exceeds {MAX_PAYLOAD_BYTES} bytes (got {size})",
            payload_size_bytes=size,
        )

    fingerprint = fingerprint_request(req.queue, req.task_name, req.payload)

    # 2. Idempotency pre-check (fast path)
    if req.idempotency_key:
        existing = await job_repository.get_by_idempotency_key(
            session, tenant_id, req.idempotency_key
        )
        if existing is not None:
            if existing.payload_fingerprint != fingerprint:
                raise IdempotencyConflictError(
                    "Idempotency key already used with a different request"
                )
            q = await queue_repository.get_by_id(session, tenant_id, existing.queue_id)
            return _submit_response(existing, q.name if q else "unknown"), True

    # 3. Resolve queue
    queue = await queue_repository.get_by_tenant_and_name(
        session, tenant_id, req.queue
    )
    if queue is None:
        raise QueueNotFoundError(f"Queue '{req.queue}' not found")
    if not queue.is_active:
        raise InvalidTransitionError(f"Queue '{req.queue}' is inactive")

    # 4. Build job + outbox event
    now = datetime.now(UTC)
    scheduled_at = req.scheduled_at or now
    status = JobStatus.QUEUED if scheduled_at <= now else JobStatus.SCHEDULED

    retry_policy_dict: dict | None = None
    max_attempts = 5
    if req.retry_policy is not None:
        retry_policy_dict = req.retry_policy.model_dump()
        max_attempts = req.retry_policy.max_attempts

    job_id = uuid4()
    job = Job(
        id=job_id,
        tenant_id=tenant_id,
        queue_id=queue.id,
        task_name=req.task_name,
        payload=req.payload,
        status=status.value,
        priority=PRIORITY_MAP[req.priority],
        attempts=0,
        max_attempts=max_attempts,
        scheduled_at=scheduled_at,
        idempotency_key=req.idempotency_key,
        payload_fingerprint=fingerprint,
        retry_policy=retry_policy_dict,
        timeout_seconds=req.timeout_seconds,
    )
    session.add(job)

    event_id = uuid4()
    await outbox_repository.create(
        session,
        event_id=event_id,
        tenant_id=tenant_id,
        event_type="job.available",
        payload={
            "event_id": str(event_id),
            "event_type": "job.available",
            "tenant_id": str(tenant_id),
            "queue_id": str(queue.id),
            "created_at": now.isoformat(),
        },
    )

    # 5. Single commit: jobs + outbox_events land atomically (INV-01)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if req.idempotency_key and "idx_jobs_idempotency" in str(exc.orig):
            # Lost the race. Fetch the winner and compare.
            existing = await job_repository.get_by_idempotency_key(
                session, tenant_id, req.idempotency_key
            )
            if existing is not None:
                if existing.payload_fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key already used with a different request"
                    ) from exc
                q = await queue_repository.get_by_id(
                    session, tenant_id, existing.queue_id
                )
                return _submit_response(existing, q.name if q else "unknown"), True
        raise

    return _submit_response(job, queue.name), False


async def get_job(
    session: AsyncSession, tenant_id: UUID, job_id: UUID
) -> JobDetail:
    row = await job_repository.get_by_id(session, tenant_id, job_id)
    if row is None:
        raise JobNotFoundError(f"Job {job_id} not found")
    return _job_to_detail(*row)


async def list_jobs(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    statuses: list[str] | None = None,
    queue_name: str | None = None,
    task_name: str | None = None,
    priority: int | None = None,
    cursor_str: str | None = None,
    limit: int = 50,
) -> JobListResponse:
    cursor = job_repository.decode_cursor(cursor_str) if cursor_str else None
    rows, next_cursor = await job_repository.list_jobs(
        session,
        tenant_id,
        statuses=statuses,
        queue_name=queue_name,
        task_name=task_name,
        priority=priority,
        cursor=cursor,
        limit=limit,
    )
    return JobListResponse(
        items=[_job_to_summary(j, qn) for j, qn in rows],
        next_cursor=next_cursor,
    )


async def cancel_job(
    session: AsyncSession, tenant_id: UUID, job_id: UUID
) -> JobDetail:
    row = await job_repository.get_by_id(session, tenant_id, job_id, lock=True)
    if row is None:
        raise JobNotFoundError(f"Job {job_id} not found")
    job, queue_name = row

    cancellable = {
        JobStatus.QUEUED.value,
        JobStatus.SCHEDULED.value,
        JobStatus.RETRY_SCHEDULED.value,
    }
    if job.status not in cancellable:
        raise InvalidTransitionError(
            f"Cannot cancel job in status '{job.status}' "
            f"(cooperative cancellation of running jobs is not supported in MVP)"
        )

    job.status = JobStatus.CANCELLED.value
    job.updated_at = datetime.now(UTC)
    await session.commit()
    return _job_to_detail(job, queue_name)
