from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DeadLetterSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    failure_reason: str | None
    final_error_type: str | None
    dead_lettered_at: datetime
    replay_count: int
    resolved_at: datetime | None


class DeadLetterDetail(DeadLetterSummary):
    job: dict[str, Any]


class DeadLetterListResponse(BaseModel):
    items: list[DeadLetterSummary]
    next_cursor: str | None = None
