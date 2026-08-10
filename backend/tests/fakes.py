"""Shared test fakes — no real DB or network involved."""


class FakeConnection:
    """Minimal stand-in for ``AsyncConnection`` (returns a fake result)."""

    def __init__(self, engine: "FakeEngine"):
        self.engine = engine
        self.closed = False

    async def execute(self, statement):  # noqa: ARG002 — statement unused in fake
        return None

    async def close(self) -> None:
        self.closed = True
        self.engine.closed_connections.append(self)


class FakeEngine:
    """Minimal async engine stand-in for retry unit tests."""

    def __init__(
        self,
        *,
        failures_before_success: int = 0,
        error: BaseException | None = None,
        fail_forever: bool = False,
    ):
        self.attempts = 0
        self.disposed = False
        self.closed_connections: list[FakeConnection] = []
        self.failures_before_success = failures_before_success
        self.error = error or OSError("connection refused")
        self.fail_forever = fail_forever

    async def connect(self) -> FakeConnection:
        self.attempts += 1
        if self.fail_forever or self.attempts <= self.failures_before_success:
            raise self.error
        return FakeConnection(self)

    async def dispose(self) -> None:
        self.disposed = True
