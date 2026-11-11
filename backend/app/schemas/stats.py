from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobCounts(BaseModel):
    total: int = 0
    queued: int = 0
    running: int = 0
    scheduled: int = 0
    retry_scheduled: int = 0
    succeeded: int = 0
    failed: int = 0
    dead_lettered: int = 0
    cancelled: int = 0


class WorkerCounts(BaseModel):
    total: int = 0
    active: int = 0
    live: int = 0


class QueueStat(BaseModel):
    id: UUID
    name: str
    is_active: bool
    max_concurrency: int
    queued: int = 0
    running: int = 0
    retry_scheduled: int = 0


class RecentFailure(BaseModel):
    id: UUID
    task_name: str
    status: str
    last_error: str | None
    updated_at: datetime


class OverviewStats(BaseModel):
    jobs: JobCounts
    workers: WorkerCounts
    queues: list[QueueStat]
    recent_failures: list[RecentFailure]
    status_vein: list[str] = []      # last 80 statuses, oldest -> newest
    throughput_60s: list[int] = []   # jobs created per second, oldest -> newest
