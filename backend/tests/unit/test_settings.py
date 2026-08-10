"""Unit tests for application settings (T1.3).

RED phase: references ``app.core.settings`` which does not exist yet.
"""

from app.core.settings import Settings, get_settings


def test_settings_defaults_match_design():
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://postgres:postgres@localhost:5432/centinela"
    assert settings.db_pool_size == 20
    assert settings.db_max_overflow == 10
    assert settings.db_pool_timeout == 5.0
    assert settings.db_pool_pre_ping is True
    assert settings.db_retry_initial_backoff == 0.5
    assert settings.db_retry_max_attempts == 3
    assert settings.db_retry_jitter == 0.25
    assert "http://localhost:5173" in settings.cors_origins


def test_settings_read_env_vars(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://ci:ci@db:5432/centinela")
    monkeypatch.setenv("DB_RETRY_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("DB_RETRY_JITTER", "0.4")
    monkeypatch.setenv("DB_POOL_SIZE", "10")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:8080"]')
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://ci:ci@db:5432/centinela"
    assert settings.db_retry_max_attempts == 5
    assert settings.db_retry_jitter == 0.4
    assert settings.db_pool_size == 10
    assert settings.cors_origins == ["http://localhost:8080"]


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
