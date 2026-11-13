"""Async client for the TaskForge HTTP API.

    from taskforge import TaskForgeClient

    async with TaskForgeClient(api_key="...") as client:
        job = await client.enqueue(
            task_name="send_welcome_email",
            queue="emails",
            payload={"recipient": "user@example.com"},
        )
        print(job.id)
"""

import os
from datetime import datetime
from typing import Any, AsyncIterator

import httpx

from taskforge.exceptions import (
    APIError,
    ConflictError,
    NotFoundError,
    TaskForgeConnectionError,
    UnauthorizedError,
    ValidationError,
)
from taskforge.types import (
    Job,
    JobDetail,
    JobStatus,
    Page,
    Priority,
    Queue,
    RetryPolicy,
    SubmitResponse,
)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 30.0

_STATUS_TO_ERROR = {
    401: UnauthorizedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
}


def _error_message(body: dict[str, Any]) -> str:
    """Extract a readable message from a FastAPI error body."""
    detail = body.get("detail") or body.get("message")
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                parts.append(str(item.get("msg") or item))
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else "unknown validation error"
    return str(detail) if detail else f"unknown error"


class TaskForgeClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        api_key = api_key or os.environ.get("TASKFORGE_API_KEY")
        if not api_key:
            raise ValueError(
                "api_key is required - pass api_key=... or set TASKFORGE_API_KEY"
            )

        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/api/v1",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> "TaskForgeClient":
        """Construct from TASKFORGE_URL and TASKFORGE_API_KEY env vars."""
        return cls(
            base_url=os.environ.get("TASKFORGE_URL", DEFAULT_BASE_URL),
            api_key=os.environ.get("TASKFORGE_API_KEY", ""),
        )

    async def __aenter__(self) -> "TaskForgeClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- HTTP helper --------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise TaskForgeConnectionError(str(exc)) from exc

        if resp.is_success:
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()

        try:
            body = resp.json()
        except Exception:
            body = {"detail": resp.text or f"HTTP {resp.status_code}"}

        error_cls = _STATUS_TO_ERROR.get(resp.status_code, APIError)
        raise error_cls(
            status_code=resp.status_code,
            code=body.get("code"),
            message=_error_message(body),
            request_id=body.get("request_id") or resp.headers.get("X-Request-ID"),
        )

    # -- Jobs ---------------------------------------------------------

    async def enqueue(
        self,
        task_name: str,
        payload: dict[str, Any],
        *,
        queue: str = "default",
        priority: Priority = "normal",
        scheduled_at: datetime | str | None = None,
        retry_policy: RetryPolicy | None = None,
        max_attempts: int | None = None,
        initial_delay_seconds: int | None = None,
        max_delay_seconds: int | None = None,
        timeout_seconds: int | None = None,
        idempotency_key: str | None = None,
    ) -> SubmitResponse:
        """Submit a job. Returns the server's 202 Accepted response."""
        if retry_policy is None:
            overrides: dict[str, Any] = {}
            if max_attempts is not None:
                overrides["max_attempts"] = max_attempts
            if initial_delay_seconds is not None:
                overrides["initial_delay_seconds"] = initial_delay_seconds
            if max_delay_seconds is not None:
                overrides["max_delay_seconds"] = max_delay_seconds
            if overrides:
                retry_policy = RetryPolicy(**overrides)

        body: dict[str, Any] = {
            "queue": queue,
            "task_name": task_name,
            "payload": payload,
            "priority": priority,
        }
        if scheduled_at is not None:
            body["scheduled_at"] = (
                scheduled_at.isoformat()
                if hasattr(scheduled_at, "isoformat")
                else scheduled_at
            )
        if retry_policy is not None:
            body["retry_policy"] = retry_policy.model_dump()
        if timeout_seconds is not None:
            body["timeout_seconds"] = timeout_seconds
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key

        data = await self._request("POST", "/jobs", json=body)
        return SubmitResponse.model_validate(data)

    async def get(self, job_id: str) -> JobDetail:
        """Fetch the full job record including payload, result, and attempts."""
        data = await self._request("GET", f"/jobs/{job_id}")
        return JobDetail.model_validate(data)

    async def list_jobs(
        self,
        *,
        status: JobStatus | list[JobStatus] | None = None,
        queue: str | None = None,
        task_name: str | None = None,
        priority: int | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> Page[Job]:
        """List jobs with filters. Returns one page."""
        params: list[tuple[str, str]] = [("limit", str(limit))]
        if status is not None:
            statuses = [status] if isinstance(status, str) else status
            params.extend(("status", s) for s in statuses)
        if queue:
            params.append(("queue", queue))
        if task_name:
            params.append(("task_name", task_name))
        if priority is not None:
            params.append(("priority", str(priority)))
        if cursor:
            params.append(("cursor", cursor))

        data = await self._request("GET", "/jobs", params=params)
        return Page[Job](
            items=[Job.model_validate(item) for item in data["items"]],
            next_cursor=data.get("next_cursor"),
        )

    async def iter_jobs(self, **filters: Any) -> AsyncIterator[Job]:
        """Iterate over all pages of matching jobs."""
        cursor: str | None = None
        while True:
            page = await self.list_jobs(cursor=cursor, **filters)
            for item in page.items:
                yield item
            if not page.next_cursor:
                break
            cursor = page.next_cursor

    async def cancel(self, job_id: str) -> JobDetail:
        """Cancel a queued/scheduled/retry_scheduled job."""
        data = await self._request("POST", f"/jobs/{job_id}/cancel")
        return JobDetail.model_validate(data)

    async def wait_for(
        self,
        job_id: str,
        *,
        poll_interval: float = 1.0,
        timeout: float = 300.0,
    ) -> JobDetail:
        """Poll until the job reaches a terminal state."""
        import asyncio

        terminal = {"succeeded", "failed", "dead_lettered", "cancelled"}
        elapsed = 0.0
        while elapsed < timeout:
            job = await self.get(job_id)
            if job.status in terminal:
                return job
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(
            f"job {job_id} did not reach terminal state within {timeout}s"
        )

    # -- Queues -------------------------------------------------------

    async def queues(self) -> list[Queue]:
        """List all queues configured for the tenant."""
        data = await self._request("GET", "/queues")
        return [Queue.model_validate(item) for item in data["items"]]

    # -- Health -------------------------------------------------------

    async def health_live(self) -> bool:
        """True if the API process responds."""
        try:
            data = await self._request("GET", "/health/live")
            return bool(data and data.get("status") == "ok")
        except TaskForgeConnectionError:
            return False

    async def health_ready(self) -> bool:
        """True if the API and its dependencies are ready."""
        try:
            data = await self._request("GET", "/health/ready")
            return bool(data and data.get("status") == "ok")
        except TaskForgeConnectionError:
            return False
