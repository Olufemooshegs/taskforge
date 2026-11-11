from typing import Any

from redis.asyncio import Redis

STREAM_PREFIX = "taskforge:dispatch:"
STREAM_MAXLEN = 10_000


def stream_name(queue_name: str) -> str:
    return f"{STREAM_PREFIX}{queue_name}"


async def publish(redis_client: Redis, queue_name: str, event: dict[str, Any]) -> str:
    """Publish a small dispatch notification. Does NOT carry the job payload."""
    fields = {k: str(v) for k, v in event.items()}
    return await redis_client.xadd(
        stream_name(queue_name),
        fields,
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
