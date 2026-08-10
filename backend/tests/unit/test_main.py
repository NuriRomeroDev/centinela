"""Lifespan probe + dispose tests (T1.4)."""

from app.core.errors import ChecksumMismatchError
from app.core.settings import Settings
from app.db.retry import RetryPolicy
from app.main import _cid, create_app
from tests.fakes import FakeEngine


def test_create_app_registers_cors_middleware_with_settings_origins():
    from app.main import create_app

    app = create_app(Settings(_env_file=None, cors_origins=["http://origin.test"]))
    cors = [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert cors, "CORSMiddleware not registered"
    assert cors[0].kwargs["allow_origins"] == ["http://origin.test"]


async def test_lifespan_probes_database_on_startup_and_disposes_on_shutdown(monkeypatch):
    from app.main import create_app

    fake = FakeEngine()
    monkeypatch.setattr("app.main.get_engine", lambda: fake)
    app = create_app()
    async with app.router.lifespan_context(app):
        assert fake.attempts == 1  # one bounded connectivity probe
        assert fake.disposed is False
    assert fake.disposed is True


def test_cid_returns_none_when_exc_is_none():
    """Covers main.py line 50: _cid(None) → None."""
    assert _cid(None) is None


def test_cid_returns_none_when_exc_has_no_correlation_id():
    """Covers main.py line 50: _cid(exc) where correlation_id attr is None/falsy."""
    exc = ChecksumMismatchError()
    exc.correlation_id = None
    assert _cid(exc) is None


async def test_integrity_error_handler_logs_and_returns_422():
    """Covers main.py lines 80-81: handler emits logger.error and returns 422."""
    import logging
    from unittest.mock import patch

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from sqlalchemy.exc import IntegrityError

    from app.main import _integrity_error_handler

    app = FastAPI()

    @app.get("/boom")
    async def boom():
        raise IntegrityError("stmt", {}, Exception("orig"))

    app.add_exception_handler(IntegrityError, _integrity_error_handler)

    from httpx import ASGITransport, AsyncClient

    with patch.object(logging.getLogger("app.main"), "error") as mock_log:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/boom")
        assert response.status_code == 422
        assert response.json()["error"]["codigo"] == "ERR_INTEGRITY_VIOLATION"
        mock_log.assert_called_once()


async def test_lifespan_survives_probe_failure_without_hanging(monkeypatch):
    from app.main import create_app

    fake = FakeEngine(fail_forever=True)
    monkeypatch.setattr("app.main.get_engine", lambda: fake)
    monkeypatch.setattr(
        "app.db.retry.default_retry_policy",
        lambda: RetryPolicy(initial_backoff=0.01, max_attempts=3, jitter=0.0),
    )
    app = create_app()
    async with app.router.lifespan_context(app):
        assert fake.attempts == 3  # bounded retries ran; boot did NOT crash
    assert fake.disposed is True
