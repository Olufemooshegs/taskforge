"""Demo handlers.

Real applications register their own via @registry.task(name=...).
"""

import asyncio
import os
from typing import Any

from app.domain.policies.retry import PermanentError
from app.workers.registry import registry


@registry.task(name="echo")
async def echo(payload: dict[str, Any]) -> dict[str, Any]:
    await asyncio.sleep(0)
    return {"echoed": payload}


@registry.task(name="noop")
async def noop(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True}


@registry.task(name="slow_echo")
async def slow_echo(payload: dict[str, Any]) -> dict[str, Any]:
    seconds = float(payload.get("seconds", 2))
    await asyncio.sleep(seconds)
    return {"slept": seconds}


@registry.task(name="always_fail")
async def always_fail(payload: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError(f"always_fail invoked with payload={payload!r}")


@registry.task(name="always_fail_permanent")
async def always_fail_permanent(payload: dict[str, Any]) -> dict[str, Any]:
    raise PermanentError(f"permanent failure: {payload!r}")


@registry.task(name="fail_then_succeed")
async def fail_then_succeed(payload: dict[str, Any]) -> dict[str, Any]:
    key = str(payload.get("key", "default"))
    n = int(payload.get("fail_times", 2))
    fail_counts[key] = fail_counts.get(key, 0) + 1
    if fail_counts[key] <= n:
        raise RuntimeError(
            f"transient failure {fail_counts[key]}/{n} for key={key}"
        )
    return {"succeeded_on_attempt": fail_counts[key], "key": key}


@registry.task(name="crash_self")
async def crash_self(payload: dict[str, Any]) -> dict[str, Any]:
    """Hard-kills the worker process (os._exit) after `seconds` seconds.

    Used to test the lease reaper. On recovery the job is retried; if
    max_attempts is exhausted it dead-letters with `worker_lost` reason.
    """
    seconds = float(payload.get("seconds", 2))
    await asyncio.sleep(seconds)
    os._exit(1)
