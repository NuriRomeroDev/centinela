"""Application settings — pydantic-settings, environment driven.

Env names follow design §6.3 (``DATABASE_URL``, ``DB_RETRY_*``, pool params,
``CORS_ORIGINS``) — no extra application prefix.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from the environment and ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Centinela API"
    environment: str = "development"
    backend_port: int = 8000
    frontend_port: int = 5173

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/centinela"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: float = 5.0
    db_pool_pre_ping: bool = True

    db_retry_initial_backoff: float = 0.5
    db_retry_max_attempts: int = 3
    db_retry_jitter: float = 0.25

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()
