"""TaskForge Python SDK.

Client for the TaskForge HTTP API and task registry for worker handlers.

Quickstart:
    from taskforge import TaskForgeClient

    async with TaskForgeClient(api_key="...") as client:
        job = await client.enqueue(
            task_name="send_welcome_email",
            queue="emails",
            payload={"recipient": "user@example.com"},
        )
        final = await client.wait_for(job.id)
        print(final.status)
"""

from taskforge.client import TaskForgeClient
from taskforge.exceptions import (
    APIError,
    ConflictError,
    NotFoundError,
    TaskForgeConnectionError,
    TaskForgeError,
    UnauthorizedError,
    ValidationError,
)
from taskforge.registry import TaskRegistry
from taskforge.types import (
    Attempt,
    Job,
    JobDetail,
    JobStatus,
    Page,
    Priority,
    Queue,
    RetryPolicy,
    SubmitResponse,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "TaskForgeClient",
    "TaskRegistry",
    "Attempt",
    "Job",
    "JobDetail",
    "JobStatus",
    "Page",
    "Priority",
    "Queue",
    "RetryPolicy",
    "SubmitResponse",
    "TaskForgeError",
    "TaskForgeConnectionError",
    "APIError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "UnauthorizedError",
]
