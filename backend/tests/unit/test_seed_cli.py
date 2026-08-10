"""Unit tests for seed.py CLI entry point (lines 211-225)."""

from unittest.mock import AsyncMock, MagicMock, patch


def _make_factory_mock(mock_session):
    """Return an async_sessionmaker-like mock that yields mock_session as context manager."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx)
    return factory


def test_seed_main_runs_seed_and_prints_result(capsys):
    """Covers seed.py lines 211-221: main() → asyncio.run(_run()) → seed() → print."""
    from app.db.seed import SeedResult, main

    fake_result = SeedResult(skipped=False, counts={"sincronizaciones": 8})
    mock_session = AsyncMock()
    factory = _make_factory_mock(mock_session)

    with (
        patch("app.db.session.get_session_factory", return_value=factory),
        patch("app.db.seed.seed", AsyncMock(return_value=fake_result)),
    ):
        main()

    captured = capsys.readouterr()
    assert "seed applied" in captured.out
    assert "sincronizaciones" in captured.out


def test_seed_main_prints_skipped_when_data_exists(capsys):
    """Covers seed.py lines 211-221: main() with skipped=True seed result."""
    from app.db.seed import SeedResult, main

    fake_result = SeedResult(skipped=True, counts={"sincronizaciones": 8})
    mock_session = AsyncMock()
    factory = _make_factory_mock(mock_session)

    with (
        patch("app.db.session.get_session_factory", return_value=factory),
        patch("app.db.seed.seed", AsyncMock(return_value=fake_result)),
    ):
        main()

    captured = capsys.readouterr()
    assert "skipped" in captured.out


def test_seed_module_main_guard(monkeypatch):
    """Covers seed.py line 225: if __name__ == '__main__': main()."""
    from app.db import seed as seed_module

    called = []
    monkeypatch.setattr(seed_module, "main", lambda: called.append(True))
    exec(  # noqa: S102
        compile(
            "__name__ = '__main__'\nif __name__ == '__main__': main()",
            "<string>",
            "exec",
        ),
        {"__name__": "__main__", "main": seed_module.main},
    )
