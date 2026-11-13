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

from importlib.metadata import PackageNotFoundError, version as _pkg_version

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

try:
    __version__ = _pkg_version("taskforge-sdk")
except PackageNotFoundError:
    # Running from a source checkout that hasn't been pip-installed.
    # Real installs (pip install taskforge-sdk or pip install -e ./sdk)
    # always resolve via package metadata.
    __version__ = "0.0.0+unknown"

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