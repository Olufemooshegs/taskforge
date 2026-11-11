import asyncio
import json
import logging
import os
import signal
import socket
import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from app.broker.consumer import RedisConsumer
from app.broker.relay import relay_loop
from app.core.config import get_settings
from app.db.session import SessionFactory, engine
from app.models.worker import Worker
from app.repositories import queue_repository
from app.workers import claim_manager, handlers  # noqa: F401 -- registers handlers
from app.workers.ack_manager import record_failure, record_success
from app.workers.executor import execute
from app.workers.lease_manager import renew_lease
from app.workers.recovery import recovery_loop
from app.workers.registry import registry

log = logging.getLogger("taskforge.worker")


class WorkerRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.worker_id: uuid.UUID = uuid.uuid4()
        self.tenant_id: uuid.UUID = uuid.UUID(self.settings.tenant_id)
        self.queue_names = [
            q.strip() for q in self.settings.worker_queues.split(",") if q.strip()
        ]
        self.queue_ids: list[uuid.UUID] = []
        self.concurrency = max(1, self.settings.worker_concurrency)
        self.stop_event = asyncio.Event()
        self.wake_event = asyncio.Event()
        self.in_flight: set[asyncio.Task] = set()

    async def startup(self) -> None:
        async with SessionFactory() as session:
            for qname in self.queue_names:
                q = await queue_repository.get_by_tenant_and_name(
                    session, self.tenant_id, qname
                )
                if q is None:
                    log.warning("queue '%s' not found for tenant, skipping", qname)
                    continue
                self.queue_ids.append(q.id)

            if not self.queue_ids:
                raise RuntimeError("worker has no resolvable queues to serve")

            session.add(
                Worker(
                    id=self.worker_id,
                    tenant_id=self.tenant_id,
                    hostname=socket.gethostname(),
                    pid=os.getpid(),
                    status="active",
                    supported_queues=self.queue_names,
                    concurrency=self.concurrency,
                    last_heartbeat_at=datetime.now(UTC),
                )
            )
            await session.commit()

        log.info(
            "worker %s started queues=%s concurrency=%d handlers=%s",
            self.worker_id,
            self.queue_names,
            self.concurrency,
            registry.names(),
        )

    async def heartbeat(self) -> None:
        while not self.stop_event.is_set():
            try:
                async with SessionFactory() as session:
                    await session.execute(
                        text("UPDATE workers SET last_heartbeat_at=now() WHERE id=:id"),
                        {"id": self.worker_id},
                    )
                    await session.commit()
            except Exception:
                log.exception("heartbeat failed")
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(),
                    timeout=self.settings.heartbeat_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

    async def scheduler_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                async with SessionFactory() as session:
                    promoted = (
                        await session.execute(
                            text("""
                                UPDATE jobs
                                SET status = 'queued', updated_at = now()
                                WHERE id IN (
                                    SELECT id FROM jobs
                                    WHERE status IN ('scheduled', 'retry_scheduled')
                                      AND scheduled_at <= now()
                                      AND queue_id = ANY(:queue_ids)
                                    ORDER BY scheduled_at ASC
                                    FOR UPDATE SKIP LOCKED
                                    LIMIT 100
                                )
                                RETURNING id, tenant_id, queue_id
                            """),
                            {"queue_ids": self.queue_ids},
                        )
                    ).all()

                    for _jid, tenant_id, queue_id in promoted:
                        event_id = uuid.uuid4()
                        await session.execute(
                            text("""
                                INSERT INTO outbox_events (
                                    id, tenant_id, event_type, payload
                                ) VALUES (
                                    :id, :tenant_id, 'job.available',
                                    CAST(:payload AS jsonb)
                                )
                            """),
                            {
                                "id": event_id,
                                "tenant_id": tenant_id,
                                "payload": json.dumps({
                                    "event_id": str(event_id),
                                    "event_type": "job.available",
                                    "tenant_id": str(tenant_id),
                                    "queue_id": str(queue_id),
                                    "created_at": datetime.now(UTC).isoformat(),
                                }),
                            },
                        )
                    if promoted:
                        log.info("scheduler promoted %d retry jobs", len(promoted))
                    await session.commit()
            except Exception:
                log.exception("scheduler cycle failed")
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def _claim_one(self) -> claim_manager.ClaimedJob | None:
        async with SessionFactory() as session:
            return await claim_manager.claim_one(
                session,
                worker_id=self.worker_id,
                queue_ids=self.queue_ids,
                lease_duration_seconds=self.settings.lease_duration_seconds,
            )

    async def _wait_or_wake(self, timeout: float) -> None:
        if self.stop_event.is_set():
            return
        if self.wake_event.is_set():
            self.wake_event.clear()
            return
        stop_task = asyncio.create_task(self.stop_event.wait())
        wake_task = asyncio.create_task(self.wake_event.wait())
        try:
            await asyncio.wait(
                [stop_task, wake_task],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for t in (stop_task, wake_task):
                if not t.done():
                    t.cancel()
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass
        if self.wake_event.is_set():
            self.wake_event.clear()

    async def _renew_loop(self, claim: claim_manager.ClaimedJob, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                async with SessionFactory() as session:
                    ok = await renew_lease(
                        session,
                        job_id=claim.job_id,
                        worker_id=self.worker_id,
                        lease_token=claim.lease_token,
                        lease_duration_seconds=self.settings.lease_duration_seconds,
                    )
                    if not ok:
                        log.warning(
                            "job %s: lease no longer ours, stopping renewal",
                            claim.job_id,
                        )
                        return
            except Exception:
                log.exception("lease renewal failed for %s", claim.job_id)
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self.settings.heartbeat_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

    async def _run_claimed(self, claim: claim_manager.ClaimedJob) -> None:
        stop_renew = asyncio.Event()
        renewer = asyncio.create_task(self._renew_loop(claim, stop_renew))
        try:
            outcome = await execute(claim)
            async with SessionFactory() as session:
                if outcome.success:
                    applied = await record_success(
                        session,
                        job_id=claim.job_id,
                        attempt_id=claim.attempt_id,
                        worker_id=self.worker_id,
                        lease_token=claim.lease_token,
                        outcome=outcome,
                    )
                else:
                    applied = await record_failure(
                        session,
                        job_id=claim.job_id,
                        attempt_id=claim.attempt_id,
                        worker_id=self.worker_id,
                        lease_token=claim.lease_token,
                        outcome=outcome,
                        retry_policy=claim.retry_policy,
                    )
            if not applied:
                log.warning("job %s: lease no longer valid, ack skipped", claim.job_id)
            else:
                log.info(
                    "job %s %s in %dms (attempt %d)%s",
                    claim.job_id,
                    "succeeded" if outcome.success else "failed",
                    outcome.duration_ms,
                    claim.attempt_number,
                    "" if outcome.success else
                    f" retryable={outcome.retryable} err={outcome.error_type}",
                )
        except Exception:
            log.exception("unhandled error running job %s", claim.job_id)
        finally:
            stop_renew.set()
            try:
                await asyncio.wait_for(renewer, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                renewer.cancel()

    async def run(self) -> None:
        await self.startup()

        consumer = RedisConsumer(
            queue_names=self.queue_names,
            wake_event=self.wake_event,
            stop_event=self.stop_event,
            worker_id=str(self.worker_id),
        )
        bg_tasks = [
            asyncio.create_task(self.heartbeat()),
            asyncio.create_task(self.scheduler_loop()),
            asyncio.create_task(relay_loop(self.stop_event)),
            asyncio.create_task(consumer.run()),
            asyncio.create_task(
                recovery_loop(
                    self.stop_event,
                    self.queue_ids,
                    self.settings.recovery_scan_interval_seconds,
                )
            ),
        ]

        log.info("worker %s entering main loop", self.worker_id)
        try:
            while not self.stop_event.is_set():
                if len(self.in_flight) >= self.concurrency:
                    await asyncio.wait(
                        self.in_flight, return_when=asyncio.FIRST_COMPLETED
                    )
                    continue
                try:
                    claim = await self._claim_one()
                except Exception:
                    log.exception("claim cycle failed")
                    await asyncio.sleep(2)
                    continue
                if claim is None:
                    await self._wait_or_wake(timeout=1.0)
                    continue
                log.info(
                    "claimed job=%s attempt=%d task=%s",
                    claim.job_id, claim.attempt_number, claim.task_name,
                )
                task = asyncio.create_task(self._run_claimed(claim))
                self.in_flight.add(task)
                task.add_done_callback(self.in_flight.discard)
        finally:
            for t in bg_tasks:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            await self.shutdown()

    async def shutdown(self) -> None:
        log.info("shutdown: %d in-flight jobs", len(self.in_flight))
        if self.in_flight:
            await asyncio.gather(*self.in_flight, return_exceptions=True)
        try:
            async with SessionFactory() as session:
                await session.execute(
                    text("UPDATE workers SET status='stopped', updated_at=now() WHERE id=:id"),
                    {"id": self.worker_id},
                )
                await session.commit()
        except Exception:
            log.exception("failed to mark worker stopped")
        await engine.dispose()
        log.info("worker %s stopped", self.worker_id)


async def _main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    runtime = WorkerRuntime()
    loop = asyncio.get_running_loop()

    def on_signal() -> None:
        log.info("signal received, initiating graceful shutdown")
        runtime.stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, on_signal)

    await runtime.run()


if __name__ == "__main__":
    asyncio.run(_main())
