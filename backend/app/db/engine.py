"""Async SQLAlchemy engine factory with tuned pool (design §4.2)."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.settings import Settings, get_settings


def create_engine_from_settings(settings: Settings | None = None) -> AsyncEngine:
    """Create the async engine; all pool params tunable via settings/env."""
    conf = settings or get_settings()
    return create_async_engine(
        conf.database_url,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=conf.db_pool_size,
        max_overflow=conf.db_max_overflow,
        pool_timeout=conf.db_pool_timeout,
        pool_pre_ping=conf.db_pool_pre_ping,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Process-wide engine (lazy, cached)."""
    return create_engine_from_settings()
