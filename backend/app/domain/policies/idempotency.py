import hashlib
import json
from typing import Any


def fingerprint_request(queue: str, task_name: str, payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 over (queue, task_name, payload).

    Same idempotency_key + same fingerprint = replay, return existing job.
    Same idempotency_key + different fingerprint = 409 conflict.
    """
    canonical = json.dumps(
        {"queue": queue, "task_name": task_name, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
