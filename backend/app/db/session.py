"""Async session factory and FastAPI dependency (design §4.2/§4.3).

Requests acquire their connection through :func:`app.db.retry.retry_acquire` —
bounded exponential backoff + jitter at acquisition — so a PostgreSQL outage
fails fast with ``PoolExhaustedError`` (→ 503 ``ERR_POOL_EXHAUSTED``) instead of
hanging. ``get_session_factory`` (process-wide engine) remains for the seed CLI.
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.engine import get_engine
from app.db.retry import retry_acquire


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory over the process-wide engine (seed CLI, tests)."""
    engine: AsyncEngine = get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Per-request session over a bounded-retry acquired connection."""
    engine: AsyncEngine = request.app.state.engine
    async with retry_acquire(engine) as conn:
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
