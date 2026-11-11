from collections.abc import Awaitable, Callable
from typing import Any

HandlerFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]


class TaskRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, HandlerFn] = {}

    def task(self, name: str):
        def decorator(fn: HandlerFn) -> HandlerFn:
            if name in self._handlers:
                raise ValueError(f"task '{name}' already registered")
            self._handlers[name] = fn
            return fn
        return decorator

    def get(self, name: str) -> HandlerFn | None:
        return self._handlers.get(name)

    def names(self) -> list[str]:
        return sorted(self._handlers.keys())


registry = TaskRegistry()
