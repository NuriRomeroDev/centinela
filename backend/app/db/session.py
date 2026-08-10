"""Async session factory and FastAPI dependency (design §4.3)."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.engine import get_engine


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory over the process-wide engine (``expire_on_commit=False``)."""
    engine: AsyncEngine = get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Per-request session dependency; closed by FastAPI after the request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
