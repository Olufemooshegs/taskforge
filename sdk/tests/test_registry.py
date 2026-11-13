import pytest

from taskforge import TaskRegistry


async def _noop(payload: dict) -> dict:
    return {}


def test_bare_decorator_uses_function_name():
    reg = TaskRegistry()

    @reg.task
    async def send_email(payload: dict) -> dict:
        return {"sent": True}

    assert "send_email" in reg
    assert reg.names() == ["send_email"]
    assert reg.get("send_email") is send_email


def test_named_decorator_uses_explicit_name():
    reg = TaskRegistry()

    @reg.task(name="custom.name")
    async def some_function(payload: dict) -> dict:
        return {}

    assert "custom.name" in reg
    assert reg.get("custom.name") is some_function
    assert "some_function" not in reg


def test_duplicate_registration_raises():
    reg = TaskRegistry()
    reg.task(name="x")(_noop)

    with pytest.raises(ValueError, match="already registered"):
        reg.task(name="x")(_noop)


def test_len_and_contains():
    reg = TaskRegistry()
    assert len(reg) == 0
    assert "missing" not in reg

    reg.task(name="a")(_noop)
    reg.task(name="b")(_noop)

    assert len(reg) == 2
    assert "a" in reg
    assert "b" in reg
    assert "c" not in reg
