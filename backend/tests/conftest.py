"""Shared integration fixtures: testcontainers PostgreSQL + alembic migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
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
        await session.execute(
            text(f"TRUNCATE {', '.join(ALL_TABLES)} RESTART IDENTITY CASCADE")
        )
        await session.commit()
        yield session
