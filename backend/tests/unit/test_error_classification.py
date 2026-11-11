"""Unit tests for executor classification (retryable vs permanent) — spec 17."""
import uuid

import pytest

from app.workers import handlers  # noqa: F401  -- registers demo handlers
from app.workers.claim_manager import ClaimedJob
from app.workers.executor import execute


def _make_claim(task_name: str, payload: dict | None = None, timeout: int = 5) -> ClaimedJob:
    return ClaimedJob(
        job_id=uuid.uuid4(),
        attempt_id=uuid.uuid4(),
        attempt_number=1,
        queue_id=uuid.uuid4(),
        task_name=task_name,
        payload=payload or {},
        retry_policy=None,
        timeout_seconds=timeout,
        lease_token=uuid.uuid4(),
        lease_generation=1,
    )


async def test_successful_handler_is_not_retryable():
    outcome = await execute(_make_claim("echo", {"x": 1}))
    assert outcome.success is True
    assert outcome.retryable is True  # default; unused on success
    assert outcome.result == {"echoed": {"x": 1}}


async def test_generic_exception_is_retryable():
    outcome = await execute(_make_claim("always_fail", {"k": 1}))
    assert outcome.success is False
    assert outcome.retryable is True
    assert outcome.error_type == "RuntimeError"


async def test_permanent_error_is_not_retryable():
    outcome = await execute(_make_claim("always_fail_permanent", {"k": 1}))
    assert outcome.success is False
    assert outcome.retryable is False
    assert outcome.error_type == "PermanentError"


async def test_unknown_task_is_permanent():
    outcome = await execute(_make_claim("no_such_task_xyz"))
    assert outcome.success is False
    assert outcome.retryable is False
    assert outcome.error_type == "unknown_task"


async def test_handler_timeout_is_retryable():
    outcome = await execute(_make_claim("slow_echo", {"seconds": 2}, timeout=1))
    assert outcome.success is False
    assert outcome.retryable is True
    assert outcome.timed_out is True
    assert outcome.error_type == "timeout"
