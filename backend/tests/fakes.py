"""Shared test fakes — no real DB or network involved."""


class FakeConnection:
    """Minimal stand-in for ``AsyncConnection`` (returns a fake result)."""

    def __init__(self, engine: "FakeEngine"):
        self.engine = engine
        self.closed = False

    async def execute(self, statement):  # noqa: ARG002 — statement unused in fake
        return None

    async def commit(self) -> None:
        """No-op: the fake probe transaction needs no real commit."""

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


class FakeEngineConnectOkExecuteFail(FakeEngine):
    """Engine whose connect() succeeds but execute() raises — covers the conn.close() branch
    in acquire_with_retry (line 86 of retry.py: conn acquired but SELECT 1 fails)."""

    def __init__(self, error: BaseException | None = None):
        super().__init__(failures_before_success=0)
        self._probe_error = error or OSError("SELECT 1 failed")

    async def connect(self) -> "FakeConnectionBadExecute":
        self.attempts += 1
        return FakeConnectionBadExecute(self, self._probe_error)


class FakeConnectionBadExecute(FakeConnection):
    """Connection that raises on execute() (simulates liveness probe failure)."""

    def __init__(self, engine: "FakeEngine", error: BaseException):
        super().__init__(engine)
        self._error = error

    async def execute(self, statement):
        raise self._error
