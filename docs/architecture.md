# TaskForge Architecture

Technical reference for the implemented system. Companion documents:
[`reliability.md`](./reliability.md) for invariants and verification,
[`../README.md`](../README.md) for setup and demo path.

---

## Purpose and scope

TaskForge is a distributed background-job processing engine. Applications
submit named tasks with JSON payloads; independent asynchronous workers
claim and execute them.

**Design principles** (protected by code, not just documented):

1. PostgreSQL is authoritative for job state.
2. Redis Streams is a dispatch transport, not a job database.
3. The transactional outbox protects the database-to-broker boundary.
4. Workers claim jobs atomically and execute outside database transactions.
5. Leases and fencing tokens protect ownership from stale workers.
6. At-least-once execution requires idempotent handler design.

**Out of scope for v1**: exactly-once execution, arbitrary remote code
execution, DAG workflows, multi-region, autoscaling.

---

## Component map

| Component | Responsibility | Source |
|---|---|---|
| FastAPI backend | HTTP API, validation, auth | `backend/app/api/v1/` |
| Job service | Submission with transactional outbox | `backend/app/services/job_service.py` |
| PostgreSQL 16 | Source of truth for all state | `backend/migrations/` |
| Redis 7 Streams | Dispatch notifications only | `backend/app/broker/` |
| Outbox relay | Publishes outbox rows to Redis | `backend/app/broker/relay.py` |
| Redis consumer | Wakes worker claim loop on notification | `backend/app/broker/consumer.py` |
| Claim manager | Atomic `FOR UPDATE SKIP LOCKED` claim | `backend/app/workers/claim_manager.py` |
| Executor | Runs handler with timeout + classification | `backend/app/workers/executor.py` |
| Ack manager | Conditional outcome write | `backend/app/workers/ack_manager.py` |
| Lease renewal | Extends `locked_until` while running | `backend/app/workers/lease_manager.py` |
| Lease reaper | Recovers expired leases | `backend/app/workers/recovery.py` |
| Scheduler loop | Promotes due jobs, writes outbox events | `backend/app/workers/runtime.py` |
| Next.js dashboard | Operational UI over the API | `dashboard/` |
| Python SDK | Typed async client | `sdk/` |

Full topology diagram: see the Mermaid "System view" in the top-level README.

---

## Data model

8 tables in PostgreSQL. Full schema is in
`backend/migrations/versions/0001_initial.py`.

| Table | Purpose |
|---|---|
| `tenants` | Multi-tenant scoping. MVP seeds one dev tenant. |
| `queues` | Named queues per tenant. `max_concurrency` is stored (enforcement is planned). |
| `jobs` | The authoritative job record. Status, priority, attempts, lease fields, payload, result. |
| `job_attempts` | One row per claim. Unique on `(job_id, attempt_number)`. |
| `workers` | Registered workers with heartbeats and concurrency. |
| `dead_letter_entries` | One row per job that exhausted retries or hit a permanent failure. |
| `outbox_events` | Transactional outbox rows. Written in the same transaction as job inserts. |
| `audit_logs` | Privileged action history (recovery, cancellation, future replay). |

Key indexes:
- `idx_jobs_claimable` — partial index on `(queue_id, priority DESC, scheduled_at, created_at) WHERE status = 'queued'`
- `idx_jobs_expired_leases` — partial on `locked_until WHERE status = 'running'`
- `idx_jobs_idempotency` — partial unique on `(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL`
- `idx_outbox_pending` — partial on `next_attempt_at WHERE published_at IS NULL`

---

## Submission flow
Producer → FastAPI → job_service.submit_job()
│
└→ BEGIN
INSERT jobs
INSERT outbox_events
COMMIT
→ 202 Accepted {job_id}

text

**Critical**: job insert and outbox event insert share one transaction.
A committed job is never lost because the outbox row didn't commit.
A rolled-back transaction leaves neither behind. See
`backend/app/services/job_service.py::submit_job`.

Idempotency: `(tenant_id, idempotency_key)` partial unique index. Same key
+ same payload fingerprint returns the existing job. Same key + different
fingerprint returns 409. Fingerprint is SHA-256 over canonical JSON of
`{queue, task_name, payload}`.

Payload size cap: 256 KiB, checked before any DB work.

---

## Dispatch: Redis Streams + polling fallback
outbox_events (pending rows)
│
│ outbox relay (500ms poll, FOR UPDATE SKIP LOCKED, lease 30s)
▼
taskforge:dispatch:{queue_name} (Redis Stream, notifications only)
│
│ XREADGROUP → ack immediately
▼
worker.wake_event.set() (nothing more — just wakes claim loop)

text

The relay batches up to 50 events, publishes each, then marks
`published_at=now()`. On connection loss, it **releases all leased rows**
(`locked_by=NULL, locked_until=NULL, next_attempt_at=now()+5s`) so they're
immediately reclaimable after reconnect. Without this release step, rows
would stay locked for the full 30s lease window — verified fixed during
development.

**Payloads never go through Redis.** The stream carries only
`{event_id, event_type, tenant_id, queue_id, created_at}`. The worker
always re-reads the authoritative job from PostgreSQL after claiming.

**Fallback**: if Redis is unreachable, the outbox relay logs a warning and
retries every 5s. The worker claim loop **also** wakes on a 1s timer even
without a notification. Jobs continue to flow via PostgreSQL polling.
This is the direct fix for the "stop Redis, jobs still process" demo
requirement.

`XAUTOCLAIM` for pending-message recovery is **not** implemented — see
"Known limitations" in the main README. Polling makes it unnecessary for
correctness.

---

## Worker runtime

Each worker is a separate process (`python -m app.workers`) with these
concurrent tasks:

| Task | Frequency | Purpose |
|---|---|---|
| Main claim loop | tight, `wake_event` or 1s | Claims, dispatches to executor |
| Heartbeat | 20s | Updates `workers.last_heartbeat_at` |
| Scheduler | 1s | Promotes `scheduled`/`retry_scheduled` → `queued` when due |
| Outbox relay | 500ms | Publishes outbox events (shared across workers via SKIP LOCKED) |
| Redis consumer | blocking XREADGROUP | Wakes claim loop on new dispatch |
| Recovery scan | 10s | Finds and recovers expired leases |
| Per-job lease renewal | 20s | Extends `locked_until` for running jobs |

Bounded by `WORKER_CONCURRENCY` (default 10). Extra claims wait until a
slot frees up rather than being discarded.

**Graceful shutdown**: SIGTERM sets `stop_event`. Claim loop exits,
in-flight handlers drain up to `stop_grace_period: 60s` (Docker-level).
Renewal task per job stops only after the handler writes its outcome.
If the handler can't finish in time, the lease expires naturally and
the reaper recovers the job.

---

## Claim transaction

Single transaction, `FOR UPDATE SKIP LOCKED`, `RETURNING` to fetch the
claimed job plus its incremented attempt number. `INSERT job_attempts`
in the same transaction as the `UPDATE jobs`. Commit before executing
the handler.

The claim SQL (`backend/app/workers/claim_manager.py::CLAIM_SQL`):

```sql
WITH candidate AS (
    SELECT id FROM jobs
    WHERE queue_id = ANY(:queue_ids)
      AND status = 'queued'
      AND scheduled_at <= now()
    ORDER BY priority DESC, scheduled_at ASC, created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE jobs SET
    status = 'running',
    locked_by = :worker_id,
    lease_token = :lease_token,
    lease_generation = lease_generation + 1,
    locked_until = now() + make_interval(secs => :lease_seconds),
    attempts = attempts + 1,
    started_at = COALESCE(started_at, now()),
    updated_at = now()
WHERE id IN (SELECT id FROM candidate)
RETURNING id, queue_id, task_name, payload, attempts,
          retry_policy, timeout_seconds, lease_generation;
FOR UPDATE SKIP LOCKED guarantees that two workers never see the same
queued row. This is the invariant that makes the whole system safe — see
INV-03 in reliability.md.

All lease comparisons use database time (now()), not worker clocks.
Lease defaults: 60s duration, 20s renewal, 10s recovery scan.

Ack transaction
Success and failure are two different paths, but both conditional on the
same fence:

sql
UPDATE jobs SET status = <new>
WHERE id = :job_id
  AND status = 'running'
  AND lease_token = :lease_token
  AND locked_by = :worker_id;
If rowcount = 0, the worker has lost ownership (another worker recovered
the lease, or an admin cancelled the job, or a clock skew edge case fired).
The worker must not write attempt data or results. It logs a warning
and moves on. This is INV-04.

Retry vs dead-letter: read attempts, max_attempts, and
retry_policy under FOR UPDATE inside the same transaction. Decision:

outcome.retryable AND attempts < max_attempts → retry_scheduled
with scheduled_at = now() + compute_backoff(attempts, retry_policy)

otherwise → dead_lettered + INSERT dead_letter_entries row

Backoff: min(max_delay, initial * multiplier^(attempt-1)), then
random.uniform(0, that) for full jitter. See
backend/app/domain/policies/retry.py.

Error classification
backend/app/workers/executor.py classifies every outcome:

Signal	Class	Retries?
Handler returns dict/None	success	—
Handler returns non-dict, non-None	invalid_result_type	no (permanent)
asyncio.TimeoutError	timeout	yes
PermanentError raised	PermanentError	no
Any other Exception	{ExceptionClass}	yes
No handler for task name	unknown_task	no (permanent)
PermanentError is exported from backend/app/domain/policies/retry.py
for handler authors who know a failure shouldn't be retried (e.g. bad
payload, missing external resource). Plain RuntimeError and other
exceptions are treated as transient and will retry.

Lease renewal and recovery
Every claimed job spawns a renewal task that runs every
HEARTBEAT_INTERVAL_SECONDS:

sql
UPDATE jobs SET
    locked_until = now() + make_interval(secs => :lease),
    updated_at = now()
WHERE id = :job_id
  AND status = 'running'
  AND lease_token = :token
  AND locked_by = :worker
If this returns rowcount=0, the worker has lost the lease — the renewal
task exits and the ack will also fail. The job is already being recovered
by another actor.

The recovery loop (backend/app/workers/recovery.py) runs every
RECOVERY_SCAN_INTERVAL_SECONDS (10s). For each running job with
locked_until < now():

Lock the row with FOR UPDATE and re-check expiry inside the transaction.

Close the open job_attempts row with status='worker_lost'.

Retry or dead-letter the same way record_failure does.

Write audit_logs row (action='worker_lost') for observability.

Commit.

The reaper will not fire on a live lease — verified with a 70-second
slow_echo job that outlives its initial 60s lease but is extended by
renewal, and a 15-second slow_echo job inspected mid-execution.

Concurrency and fencing
At most one active claim per job: FOR UPDATE SKIP LOCKED in the
claim SQL, plus status='queued' predicate. Verified with 3 workers
× 100 jobs: all attempts=1, zero duplicate (job_id, attempt_number).

Fenced writes: every ack and renewal is conditional on
(lease_token, locked_by, status='running'). A worker that lost the
lease cannot corrupt state.

No double-dead-letter: dead_letter_entries has
UNIQUE (job_id) with ON CONFLICT DO NOTHING on insert.

Outbox relay safety: FOR UPDATE SKIP LOCKED on outbox claim, and
WHERE published_at IS NULL on the terminal update — concurrent relays
can't double-publish.

Configuration
All config via environment variables. Full list in .env.example.

Group	Notable vars
API auth	API_KEY (default dev-api-key-change-me — must change before any deployment)
Tenant	TENANT_ID (must match a seeded row in tenants)
Database	DATABASE_URL (async driver — postgresql+asyncpg://...)
Redis	REDIS_URL
Worker	WORKER_CONCURRENCY, WORKER_QUEUES (comma-separated)
Lease	LEASE_DURATION_SECONDS (60), HEARTBEAT_INTERVAL_SECONDS (20), RECOVERY_SCAN_INTERVAL_SECONDS (10)
Host port mapping is remapped to avoid conflicts with other local projects:
Postgres on 5434, Redis on 6381. Inside the Docker network, services
use their standard ports (postgres:5432, redis:6379).

Boundaries
Explicitly not in v1, and the code doesn't pretend otherwise:

Exactly-once execution. At-least-once semantics. Handlers must be
idempotent for external side effects.

Weighted fair scheduling. Strict priority only (3 > 2 > 1). A
high-priority flood starves low-priority work. Documented as a known
limitation.

Per-queue concurrency caps. queues.max_concurrency is stored but
the worker doesn't honor it.

Weighted fair scheduling, XAUTOCLAIM, SSE, Prometheus, k6 — all
deferred per the top-level README's "Planned features".

Sync client. SDK is async-only.

Dead-letter replay. Rows are stored and inspectable; the
POST .../replay action isn't wired.

POST /jobs/{id}/retry. Spec endpoint; not implemented. The
failed terminal status is defined but never written.