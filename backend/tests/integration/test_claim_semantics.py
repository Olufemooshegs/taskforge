"""Claim and ack semantics: INV-03, INV-04, INV-08.

These are the invariants that make the system safe under concurrency and
worker churn. They are only meaningful against a real Postgres — mocked
tests would just verify the mock.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text

from app.db.session import SessionFactory
from app.schemas.job import JobSubmitRequest
from app.services import job_service
from app.workers import claim_manager
from app.workers.ack_manager import record_success
from app.workers.executor import ExecutionOutcome

pytestmark = pytest.mark.integration


def _success_outcome() -> ExecutionOutcome:
    return ExecutionOutcome(
        success=True,
        result={"ok": True},
        error_type=None,
        error_message=None,
        error_traceback=None,
        duration_ms=100,
    )


async def _submit_one(tenant_id, queue_name: str = "test_default") -> uuid.UUID:
    async with SessionFactory() as session:
        req = JobSubmitRequest(
            queue=queue_name, task_name="echo", payload={"x": 1}
        )
        response, _ = await job_service.submit_job(session, tenant_id, req)
    return response.job_id


async def test_concurrent_claims_exactly_one_wins(
    tenant_id, queues, test_workers
):
    """INV-03: two workers racing to claim the same job — exactly one wins."""
    job_id = await _submit_one(tenant_id)
    worker_a = test_workers["worker_a"]
    worker_b = test_workers["worker_b"]

    async def _claim(worker_id: uuid.UUID):
        async with SessionFactory() as session:
            return await claim_manager.claim_one(
                session,
                worker_id=worker_id,
                queue_ids=[queues["test_default"]],
            )

    claim_a, claim_b = await asyncio.gather(
        _claim(worker_a), _claim(worker_b)
    )

    claimed = [c for c in (claim_a, claim_b) if c is not None]
    assert len(claimed) == 1, "exactly one worker must win the claim"
    assert claimed[0].job_id == job_id

    # Only one attempt row exists
    async with SessionFactory() as session:
        count = await session.scalar(
            text("SELECT COUNT(*) FROM job_attempts WHERE job_id = :jid"),
            {"jid": job_id},
        )
    assert count == 1

    # Job owned by exactly one of the two workers
    async with SessionFactory() as session:
        row = (
            await session.execute(
                text("SELECT status, locked_by FROM jobs WHERE id = :jid"),
                {"jid": job_id},
            )
        ).one()
    assert row.status == "running"
    assert row.locked_by in (worker_a, worker_b)


async def test_stale_lease_token_cannot_ack(
    tenant_id, queues, test_workers
):
    """INV-04: a worker that lost the lease cannot write the outcome."""
    job_id = await _submit_one(tenant_id)
    worker_a = test_workers["worker_a"]

    # Worker A claims
    async with SessionFactory() as session:
        claim = await claim_manager.claim_one(
            session,
            worker_id=worker_a,
            queue_ids=[queues["test_default"]],
        )
    assert claim is not None
    stale_token = claim.lease_token

    # Simulate re-claim by another worker (lease rotated by reaper or new owner)
    worker_b = test_workers["worker_b"]
    new_token = uuid.uuid4()
    async with SessionFactory() as session:
        await session.execute(
            text("""
                UPDATE jobs SET
                    lease_token = :new_token,
                    locked_by = :worker_b,
                    locked_until = now() + interval '60 seconds'
                WHERE id = :jid
            """),
            {"new_token": new_token, "worker_b": worker_b, "jid": job_id},
        )
        await session.commit()

    # Worker A tries to ack with the STALE token
    async with SessionFactory() as session:
        applied = await record_success(
            session,
            job_id=claim.job_id,
            attempt_id=claim.attempt_id,
            worker_id=worker_a,
            lease_token=stale_token,
            outcome=_success_outcome(),
        )
    assert applied is False

    # Job is still running under worker B — no corruption
    async with SessionFactory() as session:
        status = await session.scalar(
            text("SELECT status FROM jobs WHERE id = :jid"), {"jid": job_id}
        )
    assert status == "running"


async def test_duplicate_dispatch_no_duplicate_ownership(
    tenant_id, queues, test_workers
):
    """INV-08: two dispatch notifications for the same job → one claim."""
    job_id = await _submit_one(tenant_id)
    worker_a = test_workers["worker_a"]
    worker_b = test_workers["worker_b"]

    # First dispatch → worker A claims
    async with SessionFactory() as session:
        claim_a = await claim_manager.claim_one(
            session,
            worker_id=worker_a,
            queue_ids=[queues["test_default"]],
        )
    assert claim_a is not None
    assert claim_a.job_id == job_id

    # Duplicate dispatch → worker B tries to claim
    async with SessionFactory() as session:
        claim_b = await claim_manager.claim_one(
            session,
            worker_id=worker_b,
            queue_ids=[queues["test_default"]],
        )
    assert claim_b is None, "no claimable work — job is already running"

    # Only 1 attempt row (no duplicate execution)
    async with SessionFactory() as session:
        count = await session.scalar(
            text("SELECT COUNT(*) FROM job_attempts WHERE job_id = :jid"),
            {"jid": job_id},
        )
    assert count == 1