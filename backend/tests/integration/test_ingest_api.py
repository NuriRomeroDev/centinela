"""Ingest API integration tests (T2.1, RED).

Scenarios (tasks.md T2.1 + ingest-idempotency + corruption-handling specs):
- happy path 201 + response shape
- replay 200 with ORIGINAL payload + ERR_DUPLICATE_BATCH row + no duplicate archivo
- server-generated correlation_id fallback
- checksum mismatch 422 + ERROR log row tied to correlation_id
- malformed JSON 422 ERR_JSON_MALFORMED + CRITICAL log row
- schema validation failure 422 ERR_SCHEMA_VALIDATION + WARNING log row
- invalid header 422 before the body is read
- concurrent corrupt + healthy isolation (availability preserved)
- concurrent duplicate isolation (TOCTOU-safe, single row)
"""

import asyncio
import hashlib
import uuid

from sqlalchemy import func, select

from app.models import ArchivoProcesado, LogError, Sincronizacion
from app.models.enums import NivelError

PAYLOAD = b'[{"id": 1, "monto": 100}, {"id": 2, "monto": 200}, {"id": 3, "monto": 300}]'


def _checksum(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _headers(*, correlation_id: str | None, checksum: str, tipo: str = "ventas") -> dict[str, str]:
    headers = {
        "X-File-Name": "lote_ventas_1206_01.csv",
        "X-Tipo-Archivo": tipo,
        "X-Checksum-SHA256": checksum,
    }
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    return headers


async def _count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_ingest_happy_path_returns_201_with_response_shape(api_client, db_session):
    cid = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/ingest",
        content=PAYLOAD,
        headers=_headers(correlation_id=cid, checksum=_checksum(PAYLOAD)),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["correlation_id"] == cid
    assert uuid.UUID(body["sync_id"])  # valid uuid
    assert body["estado"] == "completed"
    assert body["nombre_archivo"] == "lote_ventas_1206_01.csv"
    assert body["tipo_archivo"] == "ventas"
    assert body["checksum"] == _checksum(PAYLOAD)
    assert body["registros_totales"] == 3

    # persisted: one sync + one archivo, no error logs
    assert await _count(db_session, Sincronizacion) == 1
    assert await _count(db_session, ArchivoProcesado) == 1
    assert await _count(db_session, LogError) == 0


async def test_ingest_replay_returns_200_original_payload_and_duplicate_log(api_client, db_session):
    cid = str(uuid.uuid4())
    first = await api_client.post(
        "/api/v1/ingest",
        content=PAYLOAD,
        headers=_headers(correlation_id=cid, checksum=_checksum(PAYLOAD)),
    )
    replay = await api_client.post(
        "/api/v1/ingest",
        content=PAYLOAD,
        headers=_headers(correlation_id=cid, checksum=_checksum(PAYLOAD)),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == first.json()  # identical stored payload

    # exactly one sync + one archivo (no duplicate rows)
    assert await _count(db_session, Sincronizacion) == 1
    assert await _count(db_session, ArchivoProcesado) == 1

    # ERR_DUPLICATE_BATCH WARNING row persisted, tied to correlation_id
    log = (await db_session.scalars(select(LogError))).one()
    assert log.codigo_error == "ERR_DUPLICATE_BATCH"
    assert log.nivel_error == NivelError.warning
    assert str(log.correlation_id) == cid


async def test_ingest_without_correlation_id_uses_server_fallback(api_client, db_session):
    response = await api_client.post(
        "/api/v1/ingest",
        content=PAYLOAD,
        headers=_headers(correlation_id=None, checksum=_checksum(PAYLOAD)),
    )

    assert response.status_code == 201
    cid = response.json()["correlation_id"]
    uuid.UUID(cid)  # server-generated UUID echoed back

    stored = (await db_session.scalars(select(Sincronizacion))).one()
    assert str(stored.correlation_id) == cid


async def test_ingest_checksum_mismatch_returns_422_with_log_row(api_client, db_session):
    cid = str(uuid.uuid4())
    wrong_checksum = "0" * 64
    response = await api_client.post(
        "/api/v1/ingest",
        content=PAYLOAD,
        headers=_headers(correlation_id=cid, checksum=wrong_checksum),
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["codigo"] == "ERR_CHECKSUM_MISMATCH"
    assert error["correlation_id"] == cid

    # ERROR log row tied to correlation_id; NO archivo row created
    log = (await db_session.scalars(select(LogError))).one()
    assert log.codigo_error == "ERR_CHECKSUM_MISMATCH"
    assert log.nivel_error == NivelError.error
    assert str(log.correlation_id) == cid
    assert await _count(db_session, ArchivoProcesado) == 0


async def test_ingest_malformed_json_returns_422_err_json_malformed(api_client, db_session):
    cid = str(uuid.uuid4())
    body = b'{"broken": json, not valid'
    response = await api_client.post(
        "/api/v1/ingest",
        content=body,
        headers=_headers(correlation_id=cid, checksum=_checksum(body)),
    )

    assert response.status_code == 422
    assert response.json()["error"]["codigo"] == "ERR_JSON_MALFORMED"

    log = (await db_session.scalars(select(LogError))).one()
    assert log.codigo_error == "ERR_JSON_MALFORMED"
    assert log.nivel_error == NivelError.critical
    assert str(log.correlation_id) == cid
    assert await _count(db_session, ArchivoProcesado) == 0


async def test_ingest_schema_validation_failure_returns_422(api_client, db_session):
    cid = str(uuid.uuid4())
    body = b'{"tipo": "ventas", "registros": 10}'  # valid JSON but NOT a list of records
    response = await api_client.post(
        "/api/v1/ingest",
        content=body,
        headers=_headers(correlation_id=cid, checksum=_checksum(body)),
    )

    assert response.status_code == 422
    assert response.json()["error"]["codigo"] == "ERR_SCHEMA_VALIDATION"

    log = (await db_session.scalars(select(LogError))).one()
    assert log.codigo_error == "ERR_SCHEMA_VALIDATION"
    assert log.nivel_error == NivelError.warning
    assert str(log.correlation_id) == cid


async def test_ingest_invalid_header_returns_422_before_reading_body(api_client, db_session):
    # X-Tipo-Archivo not in the enum AND a body whose checksum would mismatch:
    # the header error MUST win (body never consumed → no checksum/log processing).
    cid = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/ingest",
        content=PAYLOAD,
        headers=_headers(correlation_id=cid, checksum="0" * 64, tipo="pdf"),
    )

    assert response.status_code == 422
    assert "error" in response.json()

    # body was never read: no sync, no archivo, no log row
    assert await _count(db_session, Sincronizacion) == 0
    assert await _count(db_session, ArchivoProcesado) == 0
    assert await _count(db_session, LogError) == 0


async def test_ingest_missing_header_returns_422(api_client):
    response = await api_client.post(
        "/api/v1/ingest",
        content=PAYLOAD,
        headers={"X-File-Name": "lote.csv", "X-Checksum-SHA256": _checksum(PAYLOAD)},  # no tipo
    )
    assert response.status_code == 422
    assert "error" in response.json()


async def test_concurrent_corrupt_and_healthy_ingests_are_isolated(api_client, db_session):
    healthy_cid = str(uuid.uuid4())
    corrupt_cid = str(uuid.uuid4())

    healthy, corrupt = await asyncio.gather(
        api_client.post(
            "/api/v1/ingest",
            content=PAYLOAD,
            headers=_headers(correlation_id=healthy_cid, checksum=_checksum(PAYLOAD)),
        ),
        api_client.post(
            "/api/v1/ingest",
            content=PAYLOAD,
            headers=_headers(correlation_id=corrupt_cid, checksum="1" * 64),
        ),
    )

    assert healthy.status_code == 201
    assert corrupt.status_code == 422
    assert corrupt.json()["error"]["codigo"] == "ERR_CHECKSUM_MISMATCH"

    # healthy sync persisted; corrupt one logged against a FAILED parent sync
    # (logs_errores.correlation_id FK requires a parent) — exactly one archivo.
    estados = set((await db_session.scalars(select(Sincronizacion.estado))).all())
    assert estados == {"completed", "failed"}
    assert await _count(db_session, ArchivoProcesado) == 1
    assert await _count(db_session, LogError) == 1
    log = (await db_session.scalars(select(LogError))).one()
    assert str(log.correlation_id) == corrupt_cid


async def test_concurrent_duplicate_ingests_are_toctou_safe(api_client, db_session):
    cid = str(uuid.uuid4())
    results = await asyncio.gather(
        *[
            api_client.post(
                "/api/v1/ingest",
                content=PAYLOAD,
                headers=_headers(correlation_id=cid, checksum=_checksum(PAYLOAD)),
            )
            for _ in range(2)
        ]
    )

    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 201]  # one winner, one idempotent replay

    # exactly one sync + one archivo + one ERR_DUPLICATE_BATCH WARNING log
    assert await _count(db_session, Sincronizacion) == 1
    assert await _count(db_session, ArchivoProcesado) == 1
    logs = (await db_session.scalars(select(LogError))).all()
    assert [log.codigo_error for log in logs] == ["ERR_DUPLICATE_BATCH"]
    assert logs[0].nivel_error == NivelError.warning
