"""DB-outage resilience (T2.10, corruption-handling spec R3, tasks.md T2.10).

Scenarios:
- Pool exhausted: acquisition fails (fake engine raising) → request fails fast
  with 503 ERR_POOL_EXHAUSTED and bounded wall time (no hang)
- Auto-recovery: once the DB engine works again, the SAME app instance serves
  requests normally (retry lives at acquisition, never at the HTTP layer)
"""

import time
from functools import partial

from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

import app.db.session as session_module
from app.core.settings import Settings
from app.db.retry import RetryPolicy, retry_acquire
from app.main import create_app
from tests.fakes import FakeEngine

# fast policy so the test measures FAIL-FAST, not the default 1.5s backoff
FAST_POLICY = RetryPolicy(initial_backoff=0.01, max_attempts=3, jitter=0)

DB_DOWN = OperationalError("SELECT 1", None, Exception("connection refused"))


async def test_db_down_fails_fast_with_503_and_no_hang(monkeypatch):
    app = create_app(Settings(_env_file=None), engine=FakeEngine(fail_forever=True, error=DB_DOWN))
    monkeypatch.setattr(session_module, "retry_acquire", partial(retry_acquire, policy=FAST_POLICY))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = time.monotonic()
        response = await client.get("/api/v1/dashboard/metrics")
        elapsed = time.monotonic() - start

    assert response.status_code == 503
    assert response.json()["error"]["codigo"] == "ERR_POOL_EXHAUSTED"
    assert elapsed < 2.0  # bounded: ~3 attempts × 10ms backoff, never hangs


async def test_db_down_then_recovery_serves_requests_again(db_engine, clean_db, monkeypatch):
    app = create_app(Settings(_env_file=None), engine=FakeEngine(fail_forever=True, error=DB_DOWN))
    monkeypatch.setattr(session_module, "retry_acquire", partial(retry_acquire, policy=FAST_POLICY))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/dashboard/metrics")).status_code == 503

        # DB "returns": same app instance, engine swapped back to the live one
        app.state.engine = db_engine
        response = await client.get("/api/v1/dashboard/metrics")

    assert response.status_code == 200
    assert response.json()["sincronizaciones_activas"] == 0
