from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NullPool is used deliberately:
# - Each session opens a fresh connection, eliminating event-loop cross-
#   contamination in tests (pytest-asyncio creates a new loop per test, and
#   pooled connections bound to a dead loop break the next test).
# - The workload is bounded: worker concurrency ~10, API concurrency low.
#   Pooling overhead is negligible; correctness is more valuable.
# - The lease reaper calls dispose() at shutdown — NullPool makes that trivial.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Yields a session bound to a request scope."""
    async with SessionFactory() as session:
        yield session