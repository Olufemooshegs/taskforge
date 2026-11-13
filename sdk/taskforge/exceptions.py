"""Typed exceptions raised by TaskForgeClient."""


class TaskForgeError(Exception):
    """Base class for all SDK errors."""


class TaskForgeConnectionError(TaskForgeError):
    """Network layer failed - the API was unreachable."""


class APIError(TaskForgeError):
    """Server returned a non-2xx response."""

    def __init__(
        self,
        status_code: int,
        code: str | None,
        message: str,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(f"[{status_code}] {code or 'error'}: {message}")


class NotFoundError(APIError):
    """404 - resource does not exist."""


class ConflictError(APIError):
    """409 - state conflict (idempotency mismatch, invalid transition, ...)."""


class ValidationError(APIError):
    """422 - request payload failed validation."""


class UnauthorizedError(APIError):
    """401 - missing or invalid API key."""
