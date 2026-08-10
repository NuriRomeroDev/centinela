"""Unit tests for get_session_factory (session.py lines 22-23)."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session_factory


def test_get_session_factory_returns_async_sessionmaker():
    """Covers session.py lines 22-23: factory body (get_engine + async_sessionmaker)."""
    get_session_factory.cache_clear()
    factory = get_session_factory()
    assert isinstance(factory, async_sessionmaker)
    assert factory.class_ is AsyncSession


def test_get_session_factory_is_cached():
    """lru_cache: repeated calls return the same object."""
    get_session_factory.cache_clear()
    first = get_session_factory()
    second = get_session_factory()
    assert first is second
