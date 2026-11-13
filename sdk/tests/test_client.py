"""Tests for TaskForgeClient using httpx.MockTransport."""

import json
from typing import Any, Callable

import httpx
import pytest

from taskforge import (
    ConflictError,
    Job,
    JobDetail,
    NotFoundError,
    Page,
    RetryPolicy,
    SubmitResponse,
    TaskForgeClient,
    TaskForgeConnectionError,
    UnauthorizedError,
    ValidationError,
)

JOB_ID = "11111111-1111-1111-1111-111111111111"
QUEUE_ID = "00000000-0000-0000-0000-000000000101"
CREATED = "2026-11-11T15:00:00+00:00"

SUBMIT_BODY = {
    "job_id": JOB_ID,
    "status": "queued",
    "queue": "emails",
    "task_name": "send_welcome_email",
    "created_at": CREATED,
}

SUMMARY_BODY = {
    "id": JOB_ID,
    "queue": "emails",
    "task_name": "send_welcome_email",
    "status": "queued",
    "priority": 2,
    "attempts": 0,
    "max_attempts": 5,
    "scheduled_at": CREATED,
    "started_at": None,
    "completed_at": None,
    "created_at": CREATED,
    "updated_at": CREATED,
}

DETAIL_BODY = {
    **SUMMARY_BODY,
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "queue_id": QUEUE_ID,
    "payload": {"recipient": "user@example.com"},
    "result": None,
    "last_error": None,
    "timeout_seconds": 300,
    "attempt_records": [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "attempt_number": 1,
            "status": "succeeded",
            "started_at": CREATED,
            "finished_at": CREATED,
            "duration_ms": 42,
            "error_type": None,
            "error_message": None,
            "error_traceback": None,
        }
    ],
}


def make_transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def make_client(transport: httpx.MockTransport) -> TaskForgeClient:
    return TaskForgeClient(
        base_url="http://test",
        api_key="test-key",
        transport=transport,
    )


# -- enqueue -------------------------------------------------------


async def test_enqueue_returns_submit_response():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        captured["api_key"] = request.headers.get("X-API-Key")
        return httpx.Response(202, json=SUBMIT_BODY)

    async with make_client(make_transport(handler)) as client:
        result = await client.enqueue(
            task_name="send_welcome_email",
            payload={"recipient": "user@example.com"},
            queue="emails",
            priority="high",
        )

    assert isinstance(result, SubmitResponse)
    assert str(result.id) == JOB_ID
    assert result.status == "queued"
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/jobs"
    assert captured["api_key"] == "test-key"
    assert captured["body"] == {
        "queue": "emails",
        "task_name": "send_welcome_email",
        "payload": {"recipient": "user@example.com"},
        "priority": "high",
    }


async def test_enqueue_with_retry_policy():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json=SUBMIT_BODY)

    async with make_client(make_transport(handler)) as client:
        await client.enqueue(
            task_name="x",
            payload={},
            retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=1),
        )

    assert captured["body"]["retry_policy"] == {
        "max_attempts": 3,
        "initial_delay_seconds": 1,
        "max_delay_seconds": 300,
        "backoff_multiplier": 2.0,
        "jitter": True,
    }


async def test_enqueue_shorthand_max_attempts():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json=SUBMIT_BODY)

    async with make_client(make_transport(handler)) as client:
        await client.enqueue(task_name="x", payload={}, max_attempts=3)

    assert captured["body"]["retry_policy"]["max_attempts"] == 3
    assert captured["body"]["retry_policy"]["initial_delay_seconds"] == 2


async def test_enqueue_with_idempotency_key():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json=SUBMIT_BODY)

    async with make_client(make_transport(handler)) as client:
        await client.enqueue(task_name="x", payload={}, idempotency_key="my-key-1")

    assert captured["body"]["idempotency_key"] == "my-key-1"


# -- get / list ----------------------------------------------------


async def test_get_job_returns_detail_with_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/jobs/{JOB_ID}"
        return httpx.Response(200, json=DETAIL_BODY)

    async with make_client(make_transport(handler)) as client:
        result = await client.get(JOB_ID)

    assert isinstance(result, JobDetail)
    assert str(result.id) == JOB_ID
    assert result.payload == {"recipient": "user@example.com"}
    assert len(result.attempt_records) == 1
    assert result.attempt_records[0].attempt_number == 1


async def test_list_jobs_returns_page():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"items": [SUMMARY_BODY], "next_cursor": "abc123"},
        )

    async with make_client(make_transport(handler)) as client:
        page = await client.list_jobs(status="queued", queue="emails", limit=10)

    assert isinstance(page, Page)
    assert len(page.items) == 1
    assert isinstance(page.items[0], Job)
    assert page.next_cursor == "abc123"


async def test_list_jobs_passes_multiple_statuses():
    from urllib.parse import parse_qs

    captured_statuses: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        qs = parse_qs(request.url.query.decode())
        captured_statuses.extend(qs.get("status", []))
        return httpx.Response(200, json={"items": [], "next_cursor": None})

    async with make_client(make_transport(handler)) as client:
        await client.list_jobs(status=["queued", "retry_scheduled"])

    assert captured_statuses == ["queued", "retry_scheduled"]


# -- cancel / wait -------------------------------------------------


async def test_cancel_job_returns_detail():
    cancelled_body = {**DETAIL_BODY, "status": "cancelled"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/jobs/{JOB_ID}/cancel"
        assert request.method == "POST"
        return httpx.Response(200, json=cancelled_body)

    async with make_client(make_transport(handler)) as client:
        result = await client.cancel(JOB_ID)

    assert result.status == "cancelled"


async def test_wait_for_returns_when_terminal():
    call_count = {"n": 0}
    success_body = {**DETAIL_BODY, "status": "succeeded"}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 3:
            return httpx.Response(200, json={**DETAIL_BODY, "status": "running"})
        return httpx.Response(200, json=success_body)

    async with make_client(make_transport(handler)) as client:
        result = await client.wait_for(JOB_ID, poll_interval=0.01, timeout=2.0)

    assert result.status == "succeeded"
    assert call_count["n"] == 3


# -- errors --------------------------------------------------------


async def test_404_raises_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"detail": "Job not found", "code": "job_not_found"}
        )

    async with make_client(make_transport(handler)) as client:
        with pytest.raises(NotFoundError) as exc_info:
            await client.get(JOB_ID)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "job_not_found"


async def test_409_raises_conflict():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "detail": "Idempotency key already used",
                "code": "idempotency_conflict",
            },
        )

    async with make_client(make_transport(handler)) as client:
        with pytest.raises(ConflictError) as exc_info:
            await client.enqueue(task_name="x", payload={}, idempotency_key="dup")

    assert exc_info.value.code == "idempotency_conflict"


async def test_422_raises_validation_error_with_flattened_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {"loc": ["body", "task_name"], "msg": "invalid task name"},
                    {"loc": ["body", "queue"], "msg": "queue required"},
                ]
            },
        )

    async with make_client(make_transport(handler)) as client:
        with pytest.raises(ValidationError) as exc_info:
            await client.enqueue(task_name="x", payload={})

    assert "invalid task name" in exc_info.value.message
    assert "queue required" in exc_info.value.message


async def test_401_raises_unauthorized():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid API key"})

    async with make_client(make_transport(handler)) as client:
        with pytest.raises(UnauthorizedError):
            await client.get(JOB_ID)


async def test_network_error_becomes_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    async with make_client(make_transport(handler)) as client:
        with pytest.raises(TaskForgeConnectionError):
            await client.get(JOB_ID)


# -- misc ----------------------------------------------------------


async def test_client_requires_api_key():
    with pytest.raises(ValueError, match="api_key is required"):
        TaskForgeClient(base_url="http://test", api_key="")


async def test_health_live_returns_bool():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    async with make_client(make_transport(handler)) as client:
        assert await client.health_live() is True
