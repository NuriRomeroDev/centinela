"""Shared integration fixtures: testcontainers PostgreSQL + alembic migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

ALL_TABLES = (
    "acciones_remediacion",
    "logs_errores",
    "archivos_procesados",
    "sincronizaciones",
)


def run_migrations(database_url: str) -> None:
    """Run ``alembic upgrade head`` programmatically against ``database_url``."""
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    """Session-scoped PostgreSQL 16 container (testcontainers)."""
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://test:test@{host}:{port}/test"


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> str:
    """Database with ``alembic upgrade head`` applied (sync — runs before any loop)."""
    run_migrations(database_url)
    return database_url


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine(migrated_database: str) -> AsyncEngine:
    engine = create_async_engine(migrated_database)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine):
    """Per-test session over a clean (truncated) database."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text(f"TRUNCATE {', '.join(ALL_TABLES)} RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session


# --- Batch 2 API fixtures (T2.1+) -------------------------------------------


@pytest_asyncio.fixture
async def clean_db(db_engine: AsyncEngine):
    """Truncate every table so each API test starts from an empty database."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text(f"TRUNCATE {', '.join(ALL_TABLES)} RESTART IDENTITY CASCADE"))
        await session.commit()


def _build_test_app(db_engine: AsyncEngine):
    """App bound to the testcontainer engine (settings only used for retry env)."""
    from app.core.settings import Settings
    from app.main import create_app

    return create_app(Settings(_env_file=None), engine=db_engine)


@pytest_asyncio.fixture
async def api_client(db_engine: AsyncEngine, clean_db):
    """httpx AsyncClient over the real app wired to the testcontainer DB."""
    app = _build_test_app(db_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def api_app(db_engine: AsyncEngine, clean_db):
    """The raw FastAPI app (for tests that need the app object, e.g. engine patching)."""
    return _build_test_app(db_engine)


@pytest_asyncio.fixture
async def query_counter(db_engine: AsyncEngine):
    """SQLAlchemy statement counter (before_cursor_execute) for N+1 assertions."""
    counter = {"statements": 0}

    def _before_cursor_execute(*_args, **_kwargs) -> None:  # noqa: ANN002, ANN003
        counter["statements"] += 1

    event.listen(db_engine.sync_engine, "before_cursor_execute", _before_cursor_execute)
    yield counter
    event.remove(db_engine.sync_engine, "before_cursor_execute", _before_cursor_execute)
