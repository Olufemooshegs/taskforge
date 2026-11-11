import re
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PriorityInput(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


PRIORITY_MAP: dict[PriorityInput, int] = {
    PriorityInput.LOW: 1,
    PriorityInput.NORMAL: 2,
    PriorityInput.HIGH: 3,
}


class RetryPolicyIn(BaseModel):
    max_attempts: int = Field(default=5, ge=1, le=50)
    initial_delay_seconds: int = Field(default=2, ge=1, le=3600)
    max_delay_seconds: int = Field(default=300, ge=1, le=86400)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    jitter: bool = True


class JobSubmitRequest(BaseModel):
    queue: str = Field(min_length=1, max_length=100)
    task_name: str = Field(min_length=1, max_length=150)
    payload: dict[str, Any]
    priority: PriorityInput = PriorityInput.NORMAL
    scheduled_at: datetime | None = None
    retry_policy: RetryPolicyIn | None = None
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    idempotency_key: str | None = Field(default=None, max_length=255)

    @field_validator("task_name")
    @classmethod
    def _validate_task_name(cls, v: str) -> str:
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]{0,149}", v):
            raise ValueError(
                "task_name must start with a letter and contain only letters, "
                "digits, '_' or '.'"
            )
        return v


class JobSubmitResponse(BaseModel):
    job_id: UUID
    status: str
    queue: str
    task_name: str
    created_at: datetime


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    queue: str
    task_name: str
    status: str
    priority: int
    attempts: int
    max_attempts: int
    scheduled_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    attempt_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    error_traceback: str | None = None


class JobDetail(JobSummary):
    tenant_id: UUID
    queue_id: UUID
    payload: dict[str, Any]
    result: dict[str, Any] | None
    last_error: str | None
    timeout_seconds: int
    attempt_records: list[AttemptSummary] = []


class JobListResponse(BaseModel):
    items: list[JobSummary]
    next_cursor: str | None = None


class QueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    max_concurrency: int
    is_active: bool
    created_at: datetime


class QueueListResponse(BaseModel):
    items: list[QueueResponse]
