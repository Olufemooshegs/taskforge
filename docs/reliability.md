# TaskForge Reliability

Every engineering invariant that makes the system safe, where it's
enforced in code, and how it's verified.

Companion: [`architecture.md`](./architecture.md) for the mechanisms,
[`../README.md`](../README.md) for the demo path.

---

## The 12 invariants

| ID | Invariant | Enforced in |
|---|---|---|
| INV-01 | A job is accepted only after its transaction commits | `services/job_service.py::submit_job` |
| INV-02 | PostgreSQL is the authoritative source of job state | every claim/ack goes through Postgres |
| INV-03 | Two workers cannot simultaneously hold a valid lease | `workers/claim_manager.py::CLAIM_SQL` |
| INV-04 | Only the current lease token may renew or acknowledge | `workers/ack_manager.py`, `workers/lease_manager.py` |
| INV-05 | Every execution attempt is recorded | `workers/claim_manager.py` (attempt insert in claim transaction) |
| INV-06 | Attempt accounting and job state changes are transactional | `workers/ack_manager.py`, `workers/recovery.py` |
| INV-07 | Terminal jobs cannot be accidentally claimed | claim SQL filters `status='queued'` |
| INV-08 | Duplicate dispatch events cannot create duplicate ownership | Postgres `status='queued'` predicate + `SKIP LOCKED` |
| INV-09 | Expired leases are eventually recovered | `workers/recovery.py` + `workers/lease_manager.py` |
| INV-10 | Redis outage does not destroy committed jobs | `broker/relay.py` (lock release on connection loss) |
| INV-11 | Idempotency keys prevent duplicate submissions | partial unique index + fingerprint check |
| INV-12 | Every API query is tenant-scoped | `core/security.py::require_tenant` |

Details on each, in order.

---

## INV-01 — Job accepted only after commit

**Where:** `backend/app/services/job_service.py::submit_job`

**What:** `INSERT jobs` and `INSERT outbox_events` occur in the same
`session.commit()`. If the transaction rolls back, neither row exists.
If it commits, both exist. The HTTP 202 is only returned after commit
returns. A crash between commit and HTTP response is safe — the job is
durable; the client retry is idempotent.

**Verified:** in the Block 3a verification script (`/tmp/verify.sh`, run
during development):
- Test 3d asserts `jobs` row exists AND `outbox_events` row exists AND
  `published_at IS NULL` after a submit
- Test 3e asserts a replay submit returns the same `job_id` and that
  `COUNT(*)` for both tables is unchanged

---

## INV-02 — PostgreSQL authoritative

**Where:** structural. There is no separate job store. The claim SQL
reads `jobs` directly, the ack SQL writes `jobs` directly. Redis is
never queried for job state.

**Verified:** by construction. Killing Redis (Block 3d verification,
`/tmp/verify_dispatch.sh` test 2) leaves jobs flowing. The worker's only
Redis interaction is XREADGROUP on the dispatch stream, and that only
sets an internal `asyncio.Event`.

---

## INV-03 — No two valid leases

**Where:** `backend/app/workers/claim_manager.py::CLAIM_SQL`

**What:** `SELECT ... FOR UPDATE SKIP LOCKED` on candidate job rows,
then `UPDATE ... WHERE id IN (SELECT id FROM candidate)`. Postgres
guarantees that two concurrent transactions cannot both lock the same
row. The second concurrent claimer skips it and picks the next one.

**Verified:** 3-worker × 100-job concurrency test during Block 3b:
- every job's `attempts = 1`
- `COUNT(job_attempts) = 100` exactly
- `COUNT(DISTINCT (job_id, attempt_number)) = 100` (no duplicates)

That test is the direct proof of this invariant under real concurrent load.

---

## INV-04 — Only current lease token may ack

**Where:** `backend/app/workers/ack_manager.py` (`record_success`,
`record_failure`), `backend/app/workers/lease_manager.py::renew_lease`

**What:** every state-changing write conditioned on
`WHERE lease_token = :token AND locked_by = :worker AND status = 'running'`.
If the WHERE produces `rowcount=0`, the worker has lost ownership. It logs
a warning and does **not** write attempt data or results.

**Verified:** every verification script (Block 3b-3d) exercises the
success path. The failure path is exercised by the reaper test
(`/tmp/verify_reaper.sh`) where the old worker's ack would fail if it
tried to write — but it can't, because `os._exit(1)` terminated the
process. The reaper takes over the lease and writes the recovery
outcome; the old worker has no chance to double-write.

A more adversarial test (kill worker, then have it try to ack from a
"zombie" state) is possible but not implemented — see Known Limitations
at the bottom.

---

## INV-05 — Every attempt recorded

**Where:** `backend/app/workers/claim_manager.py::claim_one`

**What:** the claim transaction always includes an `INSERT job_attempts`
with the incremented attempt number and `status='running'`. `UNIQUE
(job_id, attempt_number)` guarantees no duplicates. If the INSERT fails
(e.g. duplicate), the whole transaction rolls back, including the claim
UPDATE — so the job doesn't get claimed without an attempt row.

**Verified:** every verification script. Block 3c test 1 asserts
`COUNT(job_attempts) = 3` for a 3-attempt `always_fail` job. Block 3b
concurrency test asserts `COUNT = 100` for 100 jobs.

---

## INV-06 — Attempt + state change transactional

**Where:** `workers/ack_manager.py` (both `record_success` and
`record_failure`), `workers/recovery.py::_recover_one`

**What:** the ack path does `UPDATE jobs` then `UPDATE job_attempts` then
optional `INSERT dead_letter_entries`, all in one `async with session`
block, all committed together. If any step fails (e.g. the attempt UPDATE
returns `rowcount=0`), the code `await session.rollback()`s — nothing
partial is written.

The recovery path is the same structure: job UPDATE, attempt UPDATE,
optional DL insert, audit insert, all in one commit.

**Verified:** implicitly, because any partial write would break
`COUNT(*)` assertions in the verification scripts. No dedicated
"rollback happens atomically" test exists — that would require injecting
a failure mid-transaction. See Known Limitations.

---

## INV-07 — Terminal jobs not claimable

**Where:** claim SQL filters `status = 'queued'`.

**What:** terminal states are `succeeded`, `failed`, `dead_lettered`,
`cancelled`. None of these match `'queued'`, so the claim query never
returns them. A cancelled or dead-lettered job cannot be re-claimed by
any worker.

**Verified:** Block 3c test asserts `dead_lettered` jobs stay
`dead_lettered` after max attempts — they're not retried. Cancelled jobs
tested in Block 3a (`/tmp/verify.sh` test 3i).

---

## INV-08 — Duplicate dispatch no dup ownership

**Where:** structural. The dispatch notification is only a wake signal.
The actual ownership change is `UPDATE jobs SET status='running',
lease_token=... WHERE id IN (candidate FOR UPDATE SKIP LOCKED)`. If two
notifications fire for the same queue, the worker just wakes twice; the
second wake finds nothing to claim (already `running`).

**Verified:** outbox relay batches can be republished on crash-before-
ack — this is expected and safe. The consumer acks the stream message
immediately after setting `wake_event`, so duplicate stream deliveries
just wake the claim loop more often, never creating duplicate claims.

---

## INV-09 — Expired leases recovered

**Where:** `backend/app/workers/recovery.py::run_one_cycle` (called
from `recovery_loop` every 10s), plus `workers/lease_manager.py` (which
prevents false positives).

**What:**
- **Renewal** prevents jobs that are legitimately long-running (>60s)
  from being reaped. Every claimed job spawns a renewal task that
  extends `locked_until` every 20s, conditional on the lease still being
  ours.
- **Reaper** finds jobs with `status='running' AND locked_until < now()`,
  locks them, closes the open attempt as `worker_lost`, then applies the
  retry-or-dead-letter logic. All in one transaction per job.

**Verified:** `/tmp/verify_reaper.sh` (12/12 during development):
- Test 1: `slow_echo` with `seconds=70` and lease 60s. Job succeeds
  because renewal extends the lease. No `worker_lost` row exists after.
- Test 2: `crash_self` handler calls `os._exit(1)`. Job becomes
  `dead_lettered` after lease expiry + reaper tick. The closed attempt
  has `status='worker_lost'`, `error_type='worker_lost'`. A
  `dead_letter_entries` row exists. An `audit_logs` row with
  `action='worker_lost'` exists.
- Test 4: `slow_echo` with `seconds=15`, inspected at t=3s. No
  `worker_lost` row exists at that point (lease is live).

---

## INV-10 — Redis outage does not destroy committed jobs

**Where:** `backend/app/broker/relay.py::_process_batch`

**What:** the critical fix during Block 3d. When the relay claims a
batch of outbox rows and then hits `RedisConnectionError` during
publish, it must **still** run the terminal update that releases the
lease locks. Without this, rows stay locked for the full 30s lease
window and the reconnect cycle can't reclaim them.

The current code catches `RedisConnectionError` per-event, records the
failure, and always runs the `UPDATE outbox_events SET locked_by=NULL,
locked_until=NULL, next_attempt_at=now()+5s` at the end of the batch —
even when publishing failed.

**Verified:** `/tmp/verify_dispatch.sh` (10/10 during development):
- Test 2: `docker compose stop redis` → submit job → job still
  succeeds via PostgreSQL polling. Outbox backlog accumulates.
- Test 3: `docker compose start redis` → backlog drains within ~5s,
  dispatch resumes for new jobs.

Test 3 directly exercises the fix — without the terminal lock release,
the backlog would stay stuck for 30s and Test 3 would fail.

---

## INV-11 — Idempotency dedupes

**Where:** partial unique index `idx_jobs_idempotency` on
`(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL`, plus
fingerprint check in `services/job_service.py::submit_job`.

**What:**
- Same key + same payload fingerprint: return existing job (202 Accepted
  with the original job_id — idempotent replay).
- Same key + different fingerprint: 409 Conflict.
- Different key: new job.
- No key: new job (no deduplication).

Race handling: two concurrent submits with the same key will both pass
the pre-check, one wins the INSERT, the other hits an `IntegrityError`
on the unique index. The code catches that specific error, re-queries,
and returns the winner's job (or 409 if fingerprint differs).

**Verified:** `/tmp/verify.sh` (22/22 during development):
- Test 3e: same key + same payload → 202, same `job_id`, `COUNT(*) = 1`
  in both `jobs` and `outbox_events`
- Test 3f: same key + different payload → 409 with code
  `idempotency_conflict`

---

## INV-12 — Every API query tenant-scoped

**Where:** `backend/app/core/security.py::require_tenant` — every endpoint
takes a `tenant_id` parameter via Depends. Every repository query
includes `WHERE tenant_id = :tid`. Structural, not configurable.

**What:** even though the MVP seeds a single tenant, the code path for
tenant isolation exists on every read and write. Cross-tenant access is
not possible without a code change.

**Verified:** structurally — the `require_tenant` dependency returns
`UUID(settings.tenant_id)` which is a fixed seeded tenant. There are no
per-request tenant lookups, so a bug would have to explicitly remove a
`WHERE` clause. Adversarial multi-tenant tests (submit from tenant A,
query from tenant B) are not implemented — see Known Limitations.

---

## Known limitations in verification

Honest gaps in the testing story:

1. **No adversarial cross-tenant test.** The single-tenant MVP enforces
   INV-12 by construction (no per-request tenant selection), but there's
   no test that submits as tenant A and asserts tenant B can't see it.
   Blocked on multi-tenant auth being added first.

2. **No atomic-rollback test.** INV-06 (attempt + state change
   transactional) is verified indirectly — any partial write would break
   the `COUNT(*)` assertions in every verification script. A dedicated
   test would need to inject a mid-transaction failure. Not implemented.

3. **No "zombie worker tries to ack after reaper took over" test.**
   INV-04 is verified by the reaper test (`os._exit(1)` kills the worker,
   so it can't try to ack). A stronger test would pause a handler, let
   the lease expire, let the reaper take over, then resume the handler
   and assert its ack is rejected. Not implemented — requires a
   controllable handler. Documented as a plausible future test.

4. **Integration / concurrency / failure-injection tests are shell
   scripts**, not committed pytest fixtures. They're the source of truth
   for the claims in this document but require the Docker stack to be
   running. Converting them to pytest fixtures is the #1 item in the
   main README's Planned Features.

5. **`XAUTOCLAIM` for Redis pending-message recovery is not
   implemented.** Not a correctness issue — polling ensures dispatch
   within 1s even if a wake is lost. But it's a documented capability gap.

None of these are "the system might lose a job" gaps. They're "the proof
could be stronger" gaps, which is exactly what belongs in a Known
Limitations section for an MVP.