"""Unit tests for the bounded retry engine (T1.4).

RED phase: references ``app.db.retry`` / ``app.db.engine`` / ``app.db.session``
which do not exist yet. Uses a fake engine and an injected sleep recorder — no DB.
"""

import random

import pytest

from app.core.errors import PoolExhaustedError
from app.core.settings import get_settings
from app.db.retry import (
    RetryPolicy,
    acquire_with_retry,
    compute_backoff,
    default_retry_policy,
    probe_database,
    retry_acquire,
)
from tests.fakes import FakeEngine, FakeEngineConnectOkExecuteFail


class SleepRecorder:
    """Injected ``sleep`` stand-in that records requested durations."""

    def __init__(self):
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


# --- backoff parameters ------------------------------------------------------


def test_backoff_doubles_exponentially_without_jitter():
    policy = RetryPolicy(initial_backoff=0.5, max_attempts=3, jitter=0.0)
    assert compute_backoff(0, policy) == 0.5
    assert compute_backoff(1, policy) == 1.0
    assert compute_backoff(2, policy) == 2.0


def test_backoff_jitter_stays_within_bounds():
    policy = RetryPolicy(initial_backoff=0.5, max_attempts=3, jitter=0.25)
    rng = random.Random(7)
    for attempt in range(3):
        base = 0.5 * (2**attempt)
        for _ in range(50):
            value = compute_backoff(attempt, policy, rng)
            assert base - 0.25 <= value <= base + 0.25
            assert value >= 0


def test_backoff_is_deterministic_for_a_seeded_rng():
    policy = RetryPolicy(initial_backoff=1.0, max_attempts=3, jitter=0.5)
    first = compute_backoff(2, policy, random.Random(99))
    second = compute_backoff(2, policy, random.Random(99))
    assert first == second
    assert 3.5 <= first <= 4.5  # base 4.0 ± 0.5


def test_backoff_never_negative_when_jitter_exceeds_base():
    policy = RetryPolicy(initial_backoff=0.1, max_attempts=3, jitter=0.5)
    rng = random.Random(1)
    for _ in range(200):
        assert compute_backoff(0, policy, rng) >= 0


def test_default_retry_policy_matches_settings():
    settings = get_settings()
    policy = default_retry_policy()
    assert policy.initial_backoff == settings.db_retry_initial_backoff
    assert policy.max_attempts == settings.db_retry_max_attempts
    assert policy.jitter == settings.db_retry_jitter


# --- acquire_with_retry ------------------------------------------------------


async def test_acquire_succeeds_on_first_attempt_without_sleep():
    engine = FakeEngine()
    recorder = SleepRecorder()
    policy = RetryPolicy(initial_backoff=0.1, max_attempts=3, jitter=0.0)
    conn = await acquire_with_retry(engine, policy, sleep=recorder)
    try:
        assert engine.attempts == 1
        assert recorder.calls == []
    finally:
        await conn.close()


async def test_acquire_retries_with_exponential_backoff_until_success():
    engine = FakeEngine(failures_before_success=2)
    recorder = SleepRecorder()
    policy = RetryPolicy(initial_backoff=0.5, max_attempts=5, jitter=0.0)
    conn = await acquire_with_retry(engine, policy, sleep=recorder)
    try:
        assert engine.attempts == 3
        assert recorder.calls == [0.5, 1.0]  # backoff after failures 1 and 2
    finally:
        await conn.close()


async def test_acquire_fails_fast_after_max_attempts():
    engine = FakeEngine(fail_forever=True)
    recorder = SleepRecorder()
    policy = RetryPolicy(initial_backoff=0.25, max_attempts=3, jitter=0.0)
    with pytest.raises(PoolExhaustedError) as exc_info:
        await acquire_with_retry(engine, policy, sleep=recorder)
    assert engine.attempts == 3  # bounded — never loops past max_attempts
    assert recorder.calls == [0.25, 0.5]  # slept only between attempts
    assert isinstance(exc_info.value.__cause__, OSError)
    assert exc_info.value.status_code == 503
    assert exc_info.value.codigo == "ERR_POOL_EXHAUSTED"


async def test_acquire_does_not_retry_non_retryable_exceptions():
    engine = FakeEngine(error=ValueError("boom"), fail_forever=True)
    recorder = SleepRecorder()
    policy = RetryPolicy(initial_backoff=0.1, max_attempts=3, jitter=0.0)
    with pytest.raises(ValueError):
        await acquire_with_retry(engine, policy, sleep=recorder)
    assert engine.attempts == 1
    assert recorder.calls == []


async def test_no_hang_sleeps_are_exactly_bounded_by_policy():
    # The contract: bounded attempts, bounded sleeps — the request must fail
    # fast after exhaustion, never wait indefinitely.
    engine = FakeEngine(fail_forever=True)
    recorder = SleepRecorder()
    policy = RetryPolicy(initial_backoff=0.5, max_attempts=4, jitter=0.0)
    with pytest.raises(PoolExhaustedError):
        await acquire_with_retry(engine, policy, sleep=recorder)
    assert recorder.calls == [0.5, 1.0, 2.0]
    assert sum(recorder.calls) == 3.5  # finite and deterministic


async def test_retry_acquire_context_manager_closes_connection():
    engine = FakeEngine(failures_before_success=1)
    recorder = SleepRecorder()
    policy = RetryPolicy(initial_backoff=0.1, max_attempts=3, jitter=0.0)
    async with retry_acquire(engine, policy=policy, sleep=recorder) as conn:
        assert engine.attempts == 2
        assert conn.closed is False
    assert conn.closed is True
    assert engine.closed_connections == [conn]


async def test_retry_acquire_uses_default_policy():
    engine = FakeEngine()
    async with retry_acquire(engine) as conn:
        assert engine.attempts == 1
        assert conn.closed is False
    assert conn.closed is True


# --- startup probe -----------------------------------------------------------


async def test_probe_database_runs_one_bounded_probe_and_closes():
    engine = FakeEngine()
    policy = RetryPolicy(initial_backoff=0.1, max_attempts=3, jitter=0.0)
    await probe_database(engine, policy)
    assert engine.attempts == 1
    assert len(engine.closed_connections) == 1
    assert engine.closed_connections[0].closed is True


async def test_probe_database_surfaces_exhaustion_when_db_down():
    engine = FakeEngine(fail_forever=True)
    policy = RetryPolicy(initial_backoff=0.01, max_attempts=2, jitter=0.0)
    with pytest.raises(PoolExhaustedError):
        await probe_database(engine, policy)
    assert engine.attempts == 2


async def test_acquire_closes_connection_when_liveness_probe_fails():
    """Covers retry.py line 86: conn acquired but SELECT 1 raises → conn.close() called."""
    engine = FakeEngineConnectOkExecuteFail()
    recorder = SleepRecorder()
    policy = RetryPolicy(initial_backoff=0.01, max_attempts=1, jitter=0.0)
    with pytest.raises(PoolExhaustedError):
        await acquire_with_retry(engine, policy, sleep=recorder)
    assert engine.attempts == 1
    assert len(engine.closed_connections) == 1
    assert engine.closed_connections[0].closed is True
