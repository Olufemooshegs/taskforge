"""Explicit task registry for worker handlers.

Framework-agnostic: holds a dict of name -> coroutine function.

Supports three decorator forms:
    @registry.task                      # bare — uses fn.__name__
    @registry.task()                    # empty parens — same
    @registry.task(name="custom.name")  # explicit name
"""

from collections.abc import Awaitable, Callable
from typing import Any, Union

HandlerFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]


class TaskRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, HandlerFn] = {}

    def task(self, name: Union[str, HandlerFn, None] = None):
        """Decorator. Accepts bare, empty-paren, or named usage.

        Bare usage detection: if `name` is callable, `@registry.task` was
        used without parens — the function itself arrives as `name`.
        """
        # Bare usage: @registry.task  → 'name' is the function itself
        if callable(name):
            fn = name
            self._register(fn.__name__, fn)
            return fn

        # Paren usage: @registry.task() or @registry.task(name="...")
        def decorator(fn: HandlerFn) -> HandlerFn:
            self._register(name or fn.__name__, fn)
            return fn

        return decorator

    def _register(self, task_name: str, fn: HandlerFn) -> None:
        if task_name in self._handlers:
            raise ValueError(f"task {task_name!r} is already registered")
        self._handlers[task_name] = fn

    def get(self, name: str) -> HandlerFn | None:
        return self._handlers.get(name)

    def names(self) -> list[str]:
        return sorted(self._handlers.keys())

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._handlers

    def __len__(self) -> int:
        return len(self._handlers)
