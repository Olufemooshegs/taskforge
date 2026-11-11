import asyncio
import logging
import time
import uuid
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text

from app.broker.publisher import publish
from app.core.config import get_settings
from app.db.session import SessionFactory

log = logging.getLogger("taskforge.relay")

RELAY_ID = f"relay-{uuid.uuid4()}"
BATCH_SIZE = 50
POLL_INTERVAL = 0.5
RECONNECT_DELAY = 5.0
LEASE_SECONDS = 30


async def _claim_batch() -> list[tuple[uuid.UUID, uuid.UUID, str, dict[str, Any]]]:
    async with SessionFactory() as session:
        rows = (
            await session.execute(
                text("""
                    UPDATE outbox_events SET
                        locked_by = :me,
                        locked_until = now() + make_interval(secs => :lease)
                    WHERE id IN (
                        SELECT id FROM outbox_events
                        WHERE published_at IS NULL
                          AND next_attempt_at <= now()
                          AND (locked_until IS NULL OR locked_until < now())
                        ORDER BY next_attempt_at ASC, created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT :limit
                    )
                    RETURNING id, tenant_id, event_type, payload
                """),
                {"me": RELAY_ID, "lease": LEASE_SECONDS, "limit": BATCH_SIZE},
            )
        ).all()
        await session.commit()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


async def _resolve_queue_names(queue_ids: list[str]) -> dict[str, str]:
    if not queue_ids:
        return {}
    uuids = [uuid.UUID(q) for q in queue_ids]
    async with SessionFactory() as session:
        rows = (
            await session.execute(
                text("SELECT id::text, name FROM queues WHERE id = ANY(:ids)"),
                {"ids": uuids},
            )
        ).all()
    return {r[0]: r[1] for r in rows}


async def _process_batch(redis_client: Redis) -> int:
    """Publish a batch of outbox events.

    Critical: locks are ALWAYS released (published_at OR next_attempt_at bump)
    even when Redis goes down mid-batch. Without this, events stay locked for
    LEASE_SECONDS and recovery would be delayed until expiry.
    """
    batch = await _claim_batch()
    if not batch:
        return 0

    queue_ids = list({r[3].get("queue_id") for r in batch if r[3].get("queue_id")})
    queue_names = await _resolve_queue_names(queue_ids)

    published_ids: list[uuid.UUID] = []
    failed: list[tuple[uuid.UUID, str]] = []
    connection_lost = False

    for event_id, tenant_id, event_type, payload in batch:
        if connection_lost:
            failed.append((event_id, "skipped: redis connection lost"))
            continue

        queue_id = payload.get("queue_id")
        queue_name = queue_names.get(queue_id) if queue_id else None
        if queue_name is None:
            failed.append((event_id, f"queue not found: {queue_id}"))
            continue

        try:
            await publish(
                redis_client,
                queue_name,
                {
                    "event_id": str(event_id),
                    "event_type": event_type,
                    "tenant_id": str(tenant_id),
                    "queue_id": queue_id,
                    "created_at": payload.get("created_at", ""),
                },
            )
            published_ids.append(event_id)
        except RedisConnectionError as exc:
            connection_lost = True
            failed.append((event_id, f"redis: {exc.__class__.__name__}"))
        except Exception as exc:
            failed.append((event_id, f"{exc.__class__.__name__}: {exc}"[:2000]))

    # ALWAYS persist outcome -> releases every lock in this batch.
    async with SessionFactory() as session:
        if published_ids:
            await session.execute(
                text("""
                    UPDATE outbox_events SET
                        published_at = now(),
                        locked_by = NULL,
                        locked_until = NULL,
                        last_error = NULL,
                        attempt_count = attempt_count + 1
                    WHERE id = ANY(:ids) AND published_at IS NULL
                """),
                {"ids": published_ids},
            )
        for event_id, err in failed:
            await session.execute(
                text("""
                    UPDATE outbox_events SET
                        locked_by = NULL,
                        locked_until = NULL,
                        attempt_count = attempt_count + 1,
                        last_error = :err,
                        next_attempt_at = now() + interval '5 seconds'
                    WHERE id = :id
                """),
                {"err": err, "id": event_id},
            )
        await session.commit()

    if connection_lost:
        raise RedisConnectionError("connection lost during batch")

    return len(published_ids)


async def relay_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    client: Redis | None = None
    next_reconnect = 0.0

    while not stop_event.is_set():
        now = time.monotonic()

        if client is None and now >= next_reconnect:
            try:
                client = Redis.from_url(settings.redis_url, decode_responses=False)
                await client.ping()
                log.info("relay: connected to Redis")
            except Exception as exc:
                log.warning(
                    "relay: connect failed (%s); retry in %.0fs",
                    exc.__class__.__name__,
                    RECONNECT_DELAY,
                )
                if client is not None:
                    try:
                        await client.aclose()
                    except Exception:
                        pass
                    client = None
                next_reconnect = now + RECONNECT_DELAY

        if client is not None:
            try:
                n = await _process_batch(client)
                if n:
                    log.info("relay: published %d events", n)
            except RedisConnectionError as exc:
                log.warning("relay: connection lost (%s)", exc)
                try:
                    await client.aclose()
                except Exception:
                    pass
                client = None
                next_reconnect = now + RECONNECT_DELAY
            except Exception:
                log.exception("relay: batch failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass

    if client is not None:
        try:
            await client.aclose()
        except Exception:
            pass
