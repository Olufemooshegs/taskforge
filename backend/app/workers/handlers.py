import asyncio
from typing import Any

from app.domain.policies.retry import PermanentError
from app.workers.registry import registry

_fail_counts: dict[str, int] = {}


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
    _fail_counts[key] = _fail_counts.get(key, 0) + 1
    if _fail_counts[key] <= n:
        raise RuntimeError(
            f"transient failure {_fail_counts[key]}/{n} for key={key}"
        )
    return {"succeeded_on_attempt": _fail_counts[key], "key": key}
