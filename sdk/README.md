
# TaskForge SDK

Python client for the TaskForge distributed job engine.

Typed async HTTP client plus a task registry for worker handlers.

## Install

From a local checkout (the package isn't published to PyPI):

```bash
cd sdk
pip install -e ".[dev]"
```

Requires Python 3.10+ (the SDK is pure Python — no compiled dependencies).

## Quickstart

```python
import asyncio
from taskforge import TaskForgeClient


async def main():
    async with TaskForgeClient(
        base_url="http://localhost:8000",
        api_key="dev-api-key-change-me",
    ) as client:
        # Submit a job
        job = await client.enqueue(
            task_name="send_welcome_email",
            queue="emails",
            payload={"recipient": "user@example.com"},
            priority="high",
            max_attempts=5,
        )
        print(f"submitted: {job.id} ({job.status})")

        # Poll until terminal
        final = await client.wait_for(job.id, timeout=60)
        print(f"final status: {final.status}")
        if final.result:
            print(f"result: {final.result}")


asyncio.run(main())
```

Expected output:

```
submitted: <uuid> (queued)
final status: succeeded
result: {'echoed': {...}}
```

## Task registry

Register handlers on the worker side with the decorator. Three forms:

```python
from taskforge import TaskRegistry

registry = TaskRegistry()


# Form 1: bare decorator, uses fn.__name__
@registry.task
async def send_welcome_email(payload: dict) -> dict:
    recipient = payload["recipient"]
    return {"recipient": recipient, "sent": True}


# Form 2: empty parens, same behavior
@registry.task()
async def noop(payload: dict) -> dict:
    return {}


# Form 3: explicit name
@registry.task(name="custom.name")
async def any_function(payload: dict) -> dict:
    return {"ok": True}
```

The registry is framework-agnostic — it holds a dict of name → coroutine function. Feeding it into a worker loop lives in the TaskForge backend's worker process, not in this SDK.

## Error hierarchy

All exceptions inherit from `TaskForgeError`:

| Class | When |
|---|---|
| `TaskForgeConnectionError` | Network unreachable (httpx raised) |
| `APIError` | Any 4xx/5xx from the server |
| `NotFoundError` | 404 (job/queue/dead-letter missing) |
| `ConflictError` | 409 (idempotency mismatch, invalid transition) |
| `ValidationError` | 422 (payload validation) |
| `UnauthorizedError` | 401 (bad API key) |

`APIError` carries `.status_code`, `.code`, `.message`, `.request_id`. FastAPI validation errors (`422`) are flattened — the `.message` joins all per-field `msg` strings with `; `.

## Client methods

| Method | Purpose |
|---|---|
| `enqueue(task_name, payload, *, queue, priority, retry_policy, max_attempts, ...)` | Submit a job |
| `get(job_id)` | Full job detail with attempt history |
| `list_jobs(*, status, queue, task_name, priority, limit, cursor)` | Filtered list, one page |
| `iter_jobs(**filters)` | Async iterator over all pages |
| `cancel(job_id)` | Cancel queued/scheduled/retry_scheduled |
| `wait_for(job_id, *, poll_interval, timeout)` | Poll until terminal state |
| `queues()` | List queues |
| `health_live()`, `health_ready()` | Liveness / readiness booleans |

### `enqueue` — retry policy

Three ways to specify, from most to least explicit:

```python
# 1. Full RetryPolicy object
from taskforge import RetryPolicy
await client.enqueue(
    task_name="x", payload={},
    retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=5),
)

# 2. Shorthand kwargs (unset fields use server defaults)
await client.enqueue(task_name="x", payload={}, max_attempts=3)

# 3. Omit entirely (server default: 5 attempts, 2s initial delay, jitter)
await client.enqueue(task_name="x", payload={})
```

### `wait_for` — polling helper

```python
final = await client.wait_for(job_id, poll_interval=1.0, timeout=300)
```

Poll interval in seconds, timeout in seconds. Returns the `JobDetail` once `status` is one of `succeeded`, `failed`, `dead_lettered`, or `cancelled`. Raises `TimeoutError` if the job doesn't reach a terminal state in time.

### `iter_jobs` — pagination

```python
async for job in client.iter_jobs(status="dead_lettered", limit=25):
    print(job.id, job.task_name)
```

Yields across all cursor pages. `limit` controls page size, not total.

## Configuration

Two environment variables are picked up automatically by `TaskForgeClient.from_env()`:

| Variable | Default | Purpose |
|---|---|---|
| `TASKFORGE_URL` | `http://localhost:8000` | API base URL |
| `TASKFORGE_API_KEY` | (none — required) | API key for auth |

```python
from taskforge import TaskForgeClient
client = TaskForgeClient.from_env()
```

Or pass explicitly:

```python
client = TaskForgeClient(base_url="http://prod:8000", api_key="tf_...")
```

## Testing

```bash
cd sdk
pytest -q
```

20 tests, no live backend required:
- 16 client tests via `httpx.MockTransport` — verify request bodies, query params, error mapping, `wait_for` polling, connection errors
- 4 registry tests — bare decorator, named decorator, empty parens, duplicate detection

## What's not here yet

Deliberate scope limits for v0.1.0:

- **Sync client** — async only. Wrap in `asyncio.run()` for scripts.
- **Batch enqueue** — one HTTP call per job. Batch endpoint would need a server-side change first.
- **Client-side retries** — the SDK does not retry on transient 5xx. The *server* retries the *job*; the *request* is caller's responsibility.
- **Dead-letter replay** — server endpoint (`POST /dead-letters/{id}/replay`) doesn't exist yet. Once added, a `client.replay(...)` method follows.
- **`POST /jobs/{id}/retry`** — server endpoint doesn't exist yet.
- **CLI** — no `taskforge submit ...` binary. Would be a thin wrapper around the async client using `typer` or `click`.
- **PyPI publication** — `pip install taskforge-sdk` doesn't work. Install from a checkout with `pip install -e ./sdk`.

See the main repo's README for the full roadmap.

## Links

- Main project: https://github.com/Olufemooshegs/taskforge
- API docs: http://localhost:8000/docs (when running locally)
- Architecture: [`../docs/architecture.md`](../docs/architecture.md)
- Reliability: [`../docs/reliability.md`](../docs/reliability.md)
