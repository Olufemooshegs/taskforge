from datetime import datetime

from pydantic import BaseModel


class Event(BaseModel):
    id: str
    kind: str  # claimed | succeeded | failed | timed_out | worker_lost
    job_id: str
    task_name: str
    attempt_number: int
    at: datetime
    detail: str | None = None
    worker_hostname: str | None = None


class EventsResponse(BaseModel):
    items: list[Event]
