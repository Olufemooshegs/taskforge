"""Unit tests for retry backoff — spec 17."""
import pytest

from app.domain.policies.retry import compute_backoff


def test_no_jitter_is_deterministic():
    policy = {
        "initial_delay_seconds": 2.0,
        "max_delay_seconds": 300.0,
        "backoff_multiplier": 2.0,
        "jitter": False,
    }
    assert compute_backoff(1, policy) == 2.0
    assert compute_backoff(2, policy) == 4.0
    assert compute_backoff(3, policy) == 8.0
    assert compute_backoff(4, policy) == 16.0


def test_max_delay_cap():
    policy = {
        "initial_delay_seconds": 100.0,
        "max_delay_seconds": 250.0,
        "backoff_multiplier": 2.0,
        "jitter": False,
    }
    assert compute_backoff(1, policy) == 100.0
    assert compute_backoff(2, policy) == 200.0
    assert compute_backoff(3, policy) == 250.0  # capped
    assert compute_backoff(10, policy) == 250.0  # still capped


def test_jitter_stays_within_bounds():
    policy = {
        "initial_delay_seconds": 10.0,
        "max_delay_seconds": 100.0,
        "backoff_multiplier": 2.0,
        "jitter": True,
    }
    # attempt 1: cap = 10, jitter -> [0, 10]
    for _ in range(50):
        v = compute_backoff(1, policy)
        assert 0.0 <= v <= 10.0
    # attempt 4: cap = 80, jitter -> [0, 80]
    for _ in range(50):
        v = compute_backoff(4, policy)
        assert 0.0 <= v <= 80.0


def test_defaults_when_policy_is_none():
    # DEFAULT_POLICY: initial=2, mult=2, max=300, jitter=True
    for _ in range(30):
        v = compute_backoff(1, None)
        assert 0.0 <= v <= 2.0
    for _ in range(30):
        v = compute_backoff(2, None)
        assert 0.0 <= v <= 4.0


def test_policy_overrides_partial():
    # Only max_delay given; other fields from defaults
    policy = {"max_delay_seconds": 3.0, "jitter": False, "backoff_multiplier": 10.0, "initial_delay_seconds": 2.0}
    assert compute_backoff(1, policy) == 2.0
    assert compute_backoff(2, policy) == 3.0   # capped at 3
