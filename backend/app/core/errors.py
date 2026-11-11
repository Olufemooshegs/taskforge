from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    code = "domain_error"
    status_code = 400

    def __init__(self, message: str, **details):
        super().__init__(message)
        self.message = message
        self.details = details


class UnauthorizedError(DomainError):
    code = "unauthorized"
    status_code = 401


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404


class QueueNotFoundError(NotFoundError):
    code = "queue_not_found"


class JobNotFoundError(NotFoundError):
    code = "job_not_found"


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409


class IdempotencyConflictError(ConflictError):
    code = "idempotency_conflict"


class InvalidTransitionError(ConflictError):
    code = "invalid_transition"


class PayloadTooLargeError(DomainError):
    code = "payload_too_large"
    status_code = 413


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
            "request_id": getattr(request.state, "request_id", None),
            **exc.details,
        },
    )
