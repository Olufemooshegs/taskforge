from enum import IntEnum, StrEnum


class JobStatus(StrEnum):
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    CANCELLED = "cancelled"


class Priority(IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class WorkerStatus(StrEnum):
    STARTING = "starting"
    ACTIVE = "active"
    DRAINING = "draining"
    STOPPED = "stopped"


class AttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    WORKER_LOST = "worker_lost"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
