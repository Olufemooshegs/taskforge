import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.v1.health import router as health_router
from app.api.v1.dead_letters import router as dead_letters_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.queues import router as queues_router
from app.api.v1.stats import router as stats_router
from app.core.config import get_settings
from app.core.errors import DomainError, domain_error_handler
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaskForge API",
        version="0.1.0",
        description="Distributed background-job processing engine.",
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(queues_router, prefix="/api/v1")
    app.include_router(dead_letters_router, prefix="/api/v1")
    app.include_router(stats_router, prefix="/api/v1")

    _ = get_settings()  # keep import side-effect for env validation
    return app


app = create_app()
