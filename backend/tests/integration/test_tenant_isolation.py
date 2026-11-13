"""INV-12: every API query is tenant-scoped.

Proves that a job submitted by tenant A is invisible to tenant B through
every read path: get_job, list_jobs.
"""

import pytest

from app.core.errors import JobNotFoundError
from app.schemas.job import JobSubmitRequest
from app.services import job_service
from app.db.session import SessionFactory

pytestmark = pytest.mark.integration


async def test_get_job_rejects_cross_tenant_access(
    tenant_id, second_tenant_id, queues
):
    async with SessionFactory() as session:
        req = JobSubmitRequest(
            queue="test_default",
            task_name="echo",
            payload={"secret": "tenant-a-only"},
        )
        response, _ = await job_service.submit_job(session, tenant_id, req)
        job_id = response.job_id

    # Tenant A can fetch its own job
    async with SessionFactory() as session:
        detail = await job_service.get_job(session, tenant_id, job_id)
    assert detail.id == job_id

    # Tenant B cannot — 404, not a partial record
    async with SessionFactory() as session:
        with pytest.raises(JobNotFoundError):
            await job_service.get_job(session, second_tenant_id, job_id)


async def test_list_jobs_is_scoped_per_tenant(
    tenant_id, second_tenant_id, queues
):
    async with SessionFactory() as session:
        req = JobSubmitRequest(
            queue="test_default", task_name="echo", payload={"n": 1}
        )
        response, _ = await job_service.submit_job(session, tenant_id, req)
        job_id = response.job_id

    # Tenant B's list does not include tenant A's job
    async with SessionFactory() as session:
        result = await job_service.list_jobs(session, second_tenant_id)
    assert all(item.id != job_id for item in result.items)
    assert result.items == []

    # Tenant A's list does
    async with SessionFactory() as session:
        result = await job_service.list_jobs(session, tenant_id)
    assert any(item.id == job_id for item in result.items)


async def test_cross_tenant_cannot_cancel(
    tenant_id, second_tenant_id, queues
):
    async with SessionFactory() as session:
        req = JobSubmitRequest(
            queue="test_default", task_name="echo", payload={}
        )
        response, _ = await job_service.submit_job(session, tenant_id, req)
        job_id = response.job_id

    # Tenant B tries to cancel tenant A's job — 404
    async with SessionFactory() as session:
        with pytest.raises(JobNotFoundError):
            await job_service.cancel_job(session, second_tenant_id, job_id)

    # Job is still queued (not cancelled)
    async with SessionFactory() as session:
        detail = await job_service.get_job(session, tenant_id, job_id)
    assert detail.status == "queued"