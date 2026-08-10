"""Coverage gap tests targeting specific uncovered lines.

- error_logging.py: 50-52 (invalid UUID), 60→70 (parent None), 81-82 (exception swallow)
- idempotency.py: 65-72 (_load_original checksum fallback), 142 (IntegrityError race 200)
- logs.py: 38 (mensaje individual filter)
- syncs.py: 190 (unsupported remediation action)
"""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LogError, Sincronizacion
from app.models.enums import NivelError, SyncEstado
from app.services.error_logging import persist_error_log
from app.services.idempotency import _load_original, ingest_batch
from app.services.logs import list_logs
from app.services.syncs import remediate
from tests.integration.helpers import archivo_row, log_row, sync_row


# ---------------------------------------------------------------------------
# error_logging.py
# ---------------------------------------------------------------------------


async def test_persist_error_log_skips_invalid_uuid(caplog):
    """Covers error_logging.py lines 50-52: non-UUID correlation_id → early return."""
    import logging

    factory = MagicMock()
    with caplog.at_level(logging.WARNING, logger="app.services.error_logging"):
        await persist_error_log(factory, correlation_id="not-a-uuid", codigo="ERR_DB_TIMEOUT", mensaje="m")
    assert "skipping" in caplog.text
    factory.assert_not_called()


async def test_persist_error_log_creates_parent_sync_when_missing(db_session, db_factory):
    """Covers error_logging.py lines 60→70: parent sync does not exist → created."""
    fresh_cid = str(uuid.uuid4())
    await persist_error_log(
        db_factory,
        correlation_id=fresh_cid,
        codigo="ERR_DB_TIMEOUT",
        mensaje="test message",
    )
    db_session.expire_all()
    parent = await db_session.scalar(
        select(Sincronizacion).where(Sincronizacion.correlation_id == uuid.UUID(fresh_cid))
    )
    assert parent is not None
    assert parent.estado == SyncEstado.failed
    log = await db_session.scalar(
        select(LogError).where(LogError.correlation_id == uuid.UUID(fresh_cid))
    )
    assert log is not None
    assert log.codigo_error == "ERR_DB_TIMEOUT"


async def test_persist_error_log_swallows_db_exception():
    """Covers error_logging.py lines 81-82: DB exception inside factory is swallowed."""
    import app.services.error_logging as error_logging_module

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("db boom"))
    ctx.__aexit__ = AsyncMock(return_value=False)
    boom_factory = MagicMock(return_value=ctx)

    mock_logger = MagicMock()
    with patch.object(error_logging_module, "logger", mock_logger):
        await persist_error_log(
            boom_factory,
            correlation_id=str(uuid.uuid4()),
            codigo="ERR_DB_TIMEOUT",
            mensaje="m",
        )
    mock_logger.exception.assert_called_once()
    assert "failed to persist error log" in mock_logger.exception.call_args[0][0]


# ---------------------------------------------------------------------------
# idempotency.py
# ---------------------------------------------------------------------------


async def test_load_original_falls_back_to_checksum_when_correlation_id_misses(db_session, db_factory):
    """Covers idempotency.py lines 65-72: correlation_id miss → checksum lookup."""
    sync = sync_row()
    db_session.add(sync)
    await db_session.flush()
    arch = archivo_row(sync, seed="checksum-fallback-test")
    db_session.add(arch)
    await db_session.commit()

    result = await _load_original(
        db_factory,
        correlation_id=uuid.uuid4(),
        checksum=arch.checksum,
    )
    assert result is not None
    assert result.id == sync.id


async def test_ingest_batch_integrity_error_race_returns_200(db_session, db_factory):
    """Covers idempotency.py line 142: IntegrityError race → load original → 200."""
    cid = uuid.uuid4()
    sync = sync_row(correlation_id=cid)
    db_session.add(sync)
    await db_session.flush()
    checksum = hashlib.sha256(b"race-payload").hexdigest()
    arch = archivo_row(sync, seed="race-payload")
    arch.checksum = checksum
    db_session.add(arch)
    await db_session.commit()

    real_commit = AsyncSession.commit

    commit_calls = []

    async def patched_commit(self):
        if not commit_calls:
            commit_calls.append(1)
            raise IntegrityError("stmt", {}, Exception("unique violation"))
        return await real_commit(self)

    with patch.object(AsyncSession, "commit", patched_commit):
        status, body = await ingest_batch(
            db_session,
            db_factory,
            correlation_id=uuid.uuid4(),
            file_name="lote.csv",
            tipo_archivo=__import__("app.models.enums", fromlist=["TipoArchivo"]).TipoArchivo.ventas,
            checksum=checksum,
            payload=[{"id": 1}],
        )
    assert status == 200
    assert body["checksum"] == checksum


# ---------------------------------------------------------------------------
# logs.py
# ---------------------------------------------------------------------------


async def test_list_logs_mensaje_individual_filter(db_session):
    """Covers logs.py line 38: mensaje standalone filter (not search)."""
    sync = sync_row()
    db_session.add(sync)
    await db_session.flush()
    db_session.add(log_row(sync, mensaje="UNIQUE_MSG_FILTER_TEST"))
    db_session.add(log_row(sync, mensaje="other message"))
    await db_session.commit()

    result = await list_logs(db_session, mensaje="UNIQUE_MSG_FILTER_TEST")
    assert result["total"] == 1
    assert result["items"][0]["mensaje"] == "UNIQUE_MSG_FILTER_TEST"


# ---------------------------------------------------------------------------
# syncs.py
# ---------------------------------------------------------------------------


async def test_remediate_raises_for_unsupported_action(db_session):
    """Covers syncs.py line 190: unsupported accion → ValueError."""
    sync = sync_row()
    db_session.add(sync)
    await db_session.commit()

    with pytest.raises(ValueError, match="unsupported remediation action"):
        await remediate(db_session, sync_id=sync.id, accion="INVALID_ACTION")
