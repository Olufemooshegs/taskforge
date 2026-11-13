"""Shared fixtures for backend tests.

Integration tests use dedicated test tenants with fixed UUIDs so cleanup
is deterministic even if a previous run failed mid-test. The tenant delete
cascades to queues, jobs, job_attempts, outbox_events, etc.

Workers are NOT tenant-scoped at the DB level (workers.tenant_id has no FK
in the current schema — see docs/architecture.md). The test_workers fixture
therefore explicitly deletes workers before the tenant teardown, but after
job_attempts has been cascade-removed by the tenant delete.

Wait — that ordering is the other way around. job_attempts cascade from
jobs cascade from tenant, so they're gone first. Then workers can be deleted
safely (their FK from job_attempts is ON DELETE SET NULL anyway).
"""

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import text

from app.db.session import SessionFactory
from app.models.queue import Queue
from app.models.tenant import Tenant
from app.models.worker import Worker

# Fixed UUIDs so cleanup is idempotent across runs
TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
SECOND_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000098")


async def _drop_tenant(tid: uuid.UUID) -> None:
    async with SessionFactory() as session:
        await session.execute(
            text("DELETE FROM tenants WHERE id = :tid"), {"tid": tid}
        )
        await session.commit()


async def _create_tenant(tid: uuid.UUID, name: str) -> None:
    async with SessionFactory() as session:
        session.add(Tenant(id=tid, name=name, status="active"))
        await session.commit()


@pytest_asyncio.fixture
async def tenant_id():
    """Primary test tenant. Yields UUID, cleans up on teardown."""
    await _drop_tenant(TEST_TENANT_ID)
    await _create_tenant(TEST_TENANT_ID, "Test Tenant A")
    yield TEST_TENANT_ID
    await _drop_tenant(TEST_TENANT_ID)


@pytest_asyncio.fixture
async def second_tenant_id():
    """Second test tenant for cross-tenant isolation tests."""
    await _drop_tenant(SECOND_TENANT_ID)
    await _create_tenant(SECOND_TENANT_ID, "Test Tenant B")
    yield SECOND_TENANT_ID
    await _drop_tenant(SECOND_TENANT_ID)


@pytest_asyncio.fixture
async def queues(tenant_id):
    """Create test queues for the primary tenant. Returns {name: id}."""
    ids: dict[str, uuid.UUID] = {}
    async with SessionFactory() as session:
        for name in ("test_default", "test_emails"):
            q = Queue(
                tenant_id=tenant_id,
                name=name,
                max_concurrency=10,
                is_active=True,
            )
            session.add(q)
            await session.flush()
            ids[name] = q.id
        await session.commit()
    return ids


@pytest_asyncio.fixture
async def test_workers(tenant_id):
    """Two registered worker rows for concurrency tests.

    claim_one inserts into job_attempts which has an FK to workers.id, so
    callers must register the worker first. In production this happens via
    WorkerRuntime.startup(); in tests we create the rows directly.
    """
    ids: dict[str, uuid.UUID] = {}
    async with SessionFactory() as session:
        for name in ("worker_a", "worker_b"):
            w = Worker(
                tenant_id=tenant_id,
                hostname=name,
                status="active",
                supported_queues=["test_default"],
                concurrency=10,
                last_heartbeat_at=datetime.now(UTC),
            )
            session.add(w)
            await session.flush()
            ids[name] = w.id
        await session.commit()

    yield ids

    # Cleanup: delete by hostname to be safe against re-runs
    async with SessionFactory() as session:
        await session.execute(
            text("DELETE FROM workers WHERE hostname IN ('worker_a','worker_b')")
        )
        await session.commit()