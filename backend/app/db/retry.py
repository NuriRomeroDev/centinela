"""Bounded connection-acquisition retry for the async engine (design D-1).

Retries happen at ACQUISITION only — never at the HTTP layer — so side-effecting
writes are never blind-retried. Exhausted attempts fail fast with
:class:`~app.core.errors.PoolExhaustedError` (→ HTTP 503 ``ERR_POOL_EXHAUSTED``)
instead of hanging the request.
"""

import asyncio
import random
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.errors import PoolExhaustedError
from app.core.settings import get_settings

SleepFn = Callable[[float], object]

DEFAULT_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    OSError,
    asyncio.TimeoutError,
    OperationalError,
    SQLAlchemyTimeoutError,
)


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff + jitter policy for connection acquisition."""

    initial_backoff: float = 0.5
    max_attempts: int = 3
    jitter: float = 0.25
    retryable_exceptions: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE_EXCEPTIONS


def default_retry_policy() -> RetryPolicy:
    """Policy derived from settings (``DB_RETRY_*`` env vars)."""
    settings = get_settings()
    return RetryPolicy(
        initial_backoff=settings.db_retry_initial_backoff,
        max_attempts=settings.db_retry_max_attempts,
        jitter=settings.db_retry_jitter,
    )


def compute_backoff(attempt: int, policy: RetryPolicy, rng: random.Random | None = None) -> float:
    """Backoff after a failed attempt: ``initial * 2**attempt ± jitter``, clamped at 0."""
    base = policy.initial_backoff * (2**attempt)
    if policy.jitter <= 0:
        return base
    generator = rng or random
    return max(base + generator.uniform(-policy.jitter, policy.jitter), 0.0)


async def acquire_with_retry(
    engine: AsyncEngine,
    policy: RetryPolicy,
    *,
    sleep: SleepFn | None = None,
    rng: random.Random | None = None,
) -> AsyncConnection:
    """Acquire a validated connection, retrying acquisition with bounded backoff.

    Only the acquisition phase (connect + liveness probe) is retried. On
    exhaustion raises ``PoolExhaustedError``; never hangs.
    """
    sleeper = sleep or asyncio.sleep
    last_exc: BaseException | None = None
    for attempt in range(policy.max_attempts):
        conn: AsyncConnection | None = None
        try:
            conn = await engine.connect()
            await conn.execute(text("SELECT 1"))  # forces pool checkout + pre_ping
            await conn.commit()  # close the probe's implicit txn — a bound AsyncSession
            # must own its own transaction or session.commit() would not persist
            return conn
        except policy.retryable_exceptions as exc:
            last_exc = exc
            if conn is not None:
                await conn.close()
            if attempt < policy.max_attempts - 1:
                await sleeper(compute_backoff(attempt, policy, rng))
    raise PoolExhaustedError(
        f"Database connection acquisition failed after {policy.max_attempts} attempts."
    ) from last_exc


@asynccontextmanager
async def retry_acquire(
    engine: AsyncEngine,
    *,
    policy: RetryPolicy | None = None,
    sleep: SleepFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[AsyncConnection]:
    """Context manager acquiring a connection with bounded retry; closes on exit."""
    policy = policy or default_retry_policy()
    conn = await acquire_with_retry(engine, policy, sleep=sleep, rng=rng)
    try:
        yield conn
    finally:
        await conn.close()


async def probe_database(engine: AsyncEngine, policy: RetryPolicy | None = None) -> None:
    """One bounded connectivity probe for the startup lifespan (never hangs)."""
    policy = policy or default_retry_policy()
    conn = await acquire_with_retry(engine, policy)
    await conn.close()
