import random


class RetryableError(Exception):
    """Handlers raise this to explicitly signal a transient failure."""


class PermanentError(Exception):
    """Handlers raise this to explicitly signal a non-retryable failure."""


DEFAULT_POLICY = {
    "initial_delay_seconds": 2.0,
    "max_delay_seconds": 300.0,
    "backoff_multiplier": 2.0,
    "jitter": True,
}


def compute_backoff(attempt_number: int, policy: dict | None) -> float:
    """Full-jitter exponential backoff.

    delay = min(max_delay, initial * mult**(attempt-1))
    actual = random(0, delay) if jitter else delay
    attempt_number is 1-indexed (the attempt that just failed).
    """
    p = {**DEFAULT_POLICY, **(policy or {})}
    raw = float(p["initial_delay_seconds"]) * (
        float(p["backoff_multiplier"]) ** (attempt_number - 1)
    )
    capped = min(float(p["max_delay_seconds"]), raw)
    if p["jitter"]:
        return random.uniform(0.0, capped)
    return capped
