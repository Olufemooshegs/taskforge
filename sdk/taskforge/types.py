"""Typed models mirroring the TaskForge HTTP API."""

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "normal", "high"]

JobStatus = Literal[
    "scheduled",
    "queued",
    "running",
    "retry_scheduled",
    "succeeded",
    "failed",
    "dead_lettered",
    "cancelled",
]


class RetryPolicy(BaseModel):
    """Per-job retry policy. Defaults match the server."""

    max_attempts: int = Field(default=5, ge=1, le=50)
    initial_delay_seconds: int = Field(default=2, ge=1, le=3600)
    max_delay_seconds: int = Field(default=300, ge=1, le=86400)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    jitter: bool = True


class SubmitResponse(BaseModel):
    """Response from POST /jobs (202 Accepted)."""

    model_config = ConfigDict(extra="ignore")

    job_id: UUID
    status: JobStatus
    queue: str
    task_name: str
    created_at: datetime

    @property
    def id(self) -> UUID:
        """Alias for job_id, for ergonomic access."""
        return self.job_id


class Job(BaseModel):
    """Job summary as returned by GET /jobs."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    queue: str
    task_name: str
    status: JobStatus
    priority: int
    attempts: int
    max_attempts: int
    scheduled_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class Attempt(BaseModel):
    """One execution attempt of a job."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    attempt_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    error_traceback: str | None = None


class JobDetail(Job):
    """Full job record with payload, result, and attempt history."""

    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    last_error: str | None = None
    timeout_seconds: int
    attempt_records: list[Attempt] = Field(default_factory=list)


class Queue(BaseModel):
    """Queue configuration."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    max_concurrency: int
    is_active: bool
    created_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Cursor-paginated list of items."""

    items: list[T]
    next_cursor: str | None = None
