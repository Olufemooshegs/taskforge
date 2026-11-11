"""Unit tests for payload and task-name validation — spec 17."""
import pytest
from pydantic import ValidationError

from app.schemas.job import JobSubmitRequest


def _valid(**overrides) -> dict:
    base = {
        "queue": "default",
        "task_name": "send_welcome_email",
        "payload": {"recipient": "user@example.com"},
    }
    base.update(overrides)
    return base


def test_minimal_request_valid():
    req = JobSubmitRequest(**_valid())
    assert req.task_name == "send_welcome_email"
    assert req.priority == "normal"
    assert req.timeout_seconds == 300


@pytest.mark.parametrize("name", [
    "send_welcome_email",
    "my.task.v2",
    "A",
    "a_b.c.d_e",
    "t123",
])
def test_valid_task_names(name):
    req = JobSubmitRequest(**_valid(task_name=name))
    assert req.task_name == name


@pytest.mark.parametrize("name", [
    "123abc",       # starts with digit
    "_leading",     # starts with underscore
    "my task",      # space
    "my-task",      # hyphen
    "",             # empty
    "a" * 151,      # too long (>150)
])
def test_invalid_task_names(name):
    with pytest.raises(ValidationError):
        JobSubmitRequest(**_valid(task_name=name))


def test_priority_default_and_values():
    for p in ("low", "normal", "high"):
        req = JobSubmitRequest(**_valid(priority=p))
        assert req.priority == p
    with pytest.raises(ValidationError):
        JobSubmitRequest(**_valid(priority="urgent"))


def test_timeout_bounds():
    with pytest.raises(ValidationError):
        JobSubmitRequest(**_valid(timeout_seconds=0))
    with pytest.raises(ValidationError):
        JobSubmitRequest(**_valid(timeout_seconds=3601))
    req = JobSubmitRequest(**_valid(timeout_seconds=3600))
    assert req.timeout_seconds == 3600


def test_retry_policy_defaults_and_bounds():
    req = JobSubmitRequest(**_valid(retry_policy={}))
    assert req.retry_policy.max_attempts == 5
    assert req.retry_policy.initial_delay_seconds == 2

    with pytest.raises(ValidationError):
        JobSubmitRequest(**_valid(retry_policy={"max_attempts": 0}))
    with pytest.raises(ValidationError):
        JobSubmitRequest(**_valid(retry_policy={"max_attempts": 51}))
