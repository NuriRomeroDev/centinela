"""Lifespan probe + dispose tests (T1.4)."""

from app.core.settings import Settings
from app.db.retry import RetryPolicy
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
