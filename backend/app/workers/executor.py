import asyncio
import time
import traceback
from dataclasses import dataclass
from typing import Any

from app.domain.policies.retry import PermanentError
from app.workers.claim_manager import ClaimedJob
from app.workers.registry import registry


@dataclass
class ExecutionOutcome:
    success: bool
    result: dict[str, Any] | None
    error_type: str | None
    error_message: str | None
    error_traceback: str | None
    duration_ms: int
    timed_out: bool = False
    retryable: bool = True


def _fail(
    *,
    error_type: str,
    error_message: str,
    duration_ms: int,
    error_traceback: str | None = None,
    timed_out: bool = False,
    retryable: bool = True,
) -> ExecutionOutcome:
    return ExecutionOutcome(
        success=False,
        result=None,
        error_type=error_type,
        error_message=error_message,
        error_traceback=error_traceback,
        duration_ms=duration_ms,
        timed_out=timed_out,
        retryable=retryable,
    )


async def execute(job: ClaimedJob) -> ExecutionOutcome:
    handler = registry.get(job.task_name)
    if handler is None:
        return _fail(
            error_type="unknown_task",
            error_message=f"No handler registered for task '{job.task_name}'",
            duration_ms=0,
            retryable=False,
        )

    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            handler(job.payload), timeout=job.timeout_seconds
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        if result is not None and not isinstance(result, dict):
            return _fail(
                error_type="invalid_result_type",
                error_message=(
                    f"Handler returned {type(result).__name__}, expected dict or None"
                ),
                duration_ms=duration_ms,
                retryable=False,
            )
        return ExecutionOutcome(
            success=True,
            result=result,
            error_type=None,
            error_message=None,
            error_traceback=None,
            duration_ms=duration_ms,
        )
    except asyncio.TimeoutError:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _fail(
            error_type="timeout",
            error_message=f"Handler timed out after {job.timeout_seconds}s",
            duration_ms=duration_ms,
            timed_out=True,
            retryable=True,
        )
    except PermanentError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _fail(
            error_type="PermanentError",
            error_message=str(exc)[:4000],
            error_traceback=traceback.format_exc()[:16000],
            duration_ms=duration_ms,
            retryable=False,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _fail(
            error_type=exc.__class__.__name__,
            error_message=str(exc)[:4000],
            error_traceback=traceback.format_exc()[:16000],
            duration_ms=duration_ms,
            retryable=True,
        )
