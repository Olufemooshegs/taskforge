import asyncio
import logging

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.broker.publisher import stream_name
from app.core.config import get_settings

log = logging.getLogger("taskforge.consumer")

CONSUMER_GROUP = "taskforge-workers"
RECONNECT_DELAY = 5.0
XREAD_BLOCK_MS = 1000


class RedisConsumer:
    """Subscribes to dispatch streams; sets wake_event on each notification.

    The notification's only job is 'wake the claim loop'. We ack immediately.
    If XAUTOCLAIM is ever needed for stale pending messages, that's a P2
    hardening step; see spec section 3.3.
    """

    def __init__(
        self,
        *,
        queue_names: list[str],
        wake_event: asyncio.Event,
        stop_event: asyncio.Event,
        worker_id: str,
    ) -> None:
        self.queue_names = queue_names
        self.wake_event = wake_event
        self.stop_event = stop_event
        self.consumer_name = f"worker-{worker_id}"
        self.client: Redis | None = None
        self.connected = False

    async def _connect(self) -> None:
        try:
            self.client = Redis.from_url(get_settings().redis_url, decode_responses=True)
            await self.client.ping()
            for qname in self.queue_names:
                try:
                    await self.client.xgroup_create(
                        stream_name(qname),
                        CONSUMER_GROUP,
                        id="$",
                        mkstream=True,
                    )
                except ResponseError as exc:
                    if "BUSYGROUP" not in str(exc):
                        raise
            self.connected = True
            log.info("consumer: connected to Redis for %s", self.queue_names)
        except Exception as exc:
            log.warning(
                "consumer: connect failed (%s); retry in %.0fs",
                exc.__class__.__name__,
                RECONNECT_DELAY,
            )
            if self.client is not None:
                try:
                    await self.client.aclose()
                except Exception:
                    pass
                self.client = None
            self.connected = False

    async def _disconnect(self) -> None:
        if self.client is not None:
            try:
                await self.client.aclose()
            except Exception:
                pass
            self.client = None
        self.connected = False

    async def _read_loop(self) -> None:
        assert self.client is not None
        streams = {stream_name(q): ">" for q in self.queue_names}
        while not self.stop_event.is_set():
            try:
                result = await self.client.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=self.consumer_name,
                    streams=streams,
                    count=10,
                    block=XREAD_BLOCK_MS,
                )
            except Exception as exc:
                log.warning("consumer: read failed (%s)", exc.__class__.__name__)
                raise
            if not result:
                continue
            for sname, messages in result:
                for msg_id, _fields in messages:
                    self.wake_event.set()
                    try:
                        await self.client.xack(sname, CONSUMER_GROUP, msg_id)
                    except Exception:
                        pass

    async def run(self) -> None:
        while not self.stop_event.is_set():
            if not self.connected:
                await self._connect()
            if self.connected:
                try:
                    await self._read_loop()
                except Exception:
                    await self._disconnect()
            if not self.stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        self.stop_event.wait(), timeout=RECONNECT_DELAY
                    )
                except asyncio.TimeoutError:
                    pass
        await self._disconnect()
