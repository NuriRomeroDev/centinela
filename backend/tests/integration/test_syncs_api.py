"""Syncs & remediation integration tests (T2.8, RED).

Scenarios (syncs-api spec R1–R4, tasks.md T2.8):
- R1 sync list: iniciado_at DESC, full row fields, archivos_resumen computed
  server-side ("N total · M rechazados"), include_files embeds archivos;
  selectinload → constant query count on bulk data
- R2 remediation history: newest-first with correlation_id via join, N+1-free
- R3 record remediation: 201 + row persists; 422 unknown accion / missing
  ejecutado_por (no row persisted); 404 unknown sincronizacion_id
- R4 remediate: RETRY_JOB failed→running with svc.autoheal default;
  FORCE_SKIP_VALIDATION rejected→accepted; 422 unsupported; 404 unknown sync
"""

import uuid
from datetime import timedelta

from sqlalchemy import func, select

from app.models import AccionRemediacion, ArchivoProcesado, Sincronizacion
from app.models.enums import ArchivoEstado, Resultado, SyncEstado
from tests.integration.helpers import accion_row, archivo_row, sync_row, utcnow

SYNCS_URL = "/api/v1/syncs"
REMEDIATIONS_URL = "/api/v1/remediations"


async def _seed_sync_with_files(db_session, *, estado=SyncEstado.completed, rejected=0, total=3, **kw):
    sync = sync_row(estado=estado, **kw)
    db_session.add(sync)
    await db_session.flush()
    for k in range(total):
        db_session.add(
            archivo_row(
                sync,
                seed=f"{sync.correlation_id}-{k}",
                estado=ArchivoEstado.rejected if k < rejected else ArchivoEstado.accepted,
            )
        )
    await db_session.commit()
    return sync


async def test_syncs_list_with_files_ordered_newest_first(api_client, db_session):
    old = sync_row(iniciado=utcnow() - timedelta(hours=5), usuario="batch.legacy")
    db_session.add(old)
    await db_session.flush()
    new = sync_row(iniciado=utcnow() - timedelta(minutes=10))
    db_session.add(new)
    await db_session.commit()

    response = await api_client.get(SYNCS_URL, params={"include_files": "true"})
    assert response.status_code == 200
    body = response.json()

    assert [item["id"] for item in body] == [str(new.id), str(old.id)]
    first = body[0]
    assert first["correlation_id"] == str(new.correlation_id)
    assert first["estado"] == "completed"
    assert first["fecha_ejecucion"] == new.fecha_ejecucion.isoformat()
    assert first["iniciado_at"] == new.iniciado_at.isoformat()
    assert first["finalizado_at"] is None
    assert first["usuario_origen"] == "svc.batch.ops"
    assert set(first.keys()) == {
        "id", "correlation_id", "estado", "fecha_ejecucion", "iniciado_at",
        "finalizado_at", "usuario_origen", "archivos_resumen", "archivos",
    }


async def test_syncs_archivos_resumen_counts_total_and_rejected(api_client, db_session):
    sync = await _seed_sync_with_files(db_session, rejected=2, total=3)
    empty = sync_row(iniciado=utcnow() - timedelta(hours=1))
    db_session.add(empty)
    await db_session.commit()

    body = (await api_client.get(SYNCS_URL)).json()
    by_id = {item["id"]: item for item in body}

    assert by_id[str(sync.id)]["archivos_resumen"] == "3 total · 2 rechazados"
    assert by_id[str(empty.id)]["archivos_resumen"] == "0 total · 0 rechazados"


async def test_syncs_without_include_files_omits_archivos_array(api_client, db_session):
    await _seed_sync_with_files(db_session, total=3)

    body = (await api_client.get(SYNCS_URL)).json()
    assert "archivos" not in body[0]

    with_files = (await api_client.get(SYNCS_URL, params={"include_files": "true"})).json()
    archivos = with_files[0]["archivos"]
    assert len(archivos) == 3
    assert set(archivos[0].keys()) == {
        "nombre_archivo", "tipo_archivo", "checksum", "estado", "registros_totales",
    }
    assert archivos[0]["estado"] in {"accepted", "rejected"}


async def test_syncs_include_files_is_query_count_constant(api_client, db_session, query_counter):
    for i in range(60):
        await _seed_sync_with_files(db_session, estado=SyncEstado.failed if i % 3 else SyncEstado.completed, rejected=i % 3)

    query_counter["statements"] = 0  # ignore seeding; count only the request
    body = (await api_client.get(SYNCS_URL, params={"include_files": "true"})).json()

    assert len(body) == 60  # 60 syncs × 3 files = 180 files
    assert query_counter["statements"] < 10  # N+1 would be ~180 statements (selectinload: ~2)


async def test_remediations_list_newest_first_with_correlation_id(api_client, db_session, query_counter):
    syncs = [sync_row(iniciado=utcnow() - timedelta(hours=i)) for i in range(5)]
    db_session.add_all(syncs)
    await db_session.flush()
    acciones = [
        accion_row(syncs[i % 5], accion=f"ACC_{i:02d}", resultado=Resultado.success, notas=f"nota {i}",
                   ejecutada=utcnow() - timedelta(minutes=i))
        for i in range(40)
    ]
    db_session.add_all(acciones)
    await db_session.commit()
    query_counter["statements"] = 0  # ignore seeding; count only the request

    response = await api_client.get(REMEDIATIONS_URL)
    assert response.status_code == 200
    rows = response.json()

    assert len(rows) == 40
    assert [row["accion_ejecutada"] for row in rows] == [f"ACC_{i:02d}" for i in range(40)]  # newest first
    assert set(rows[0].keys()) == {
        "id", "sincronizacion_id", "correlation_id", "accion_ejecutada",
        "ejecutado_por", "resultado", "notas", "ejecutada_at",
    }
    assert rows[0]["correlation_id"] == str(syncs[0].correlation_id)
    assert query_counter["statements"] < 10  # join/selectinload: constant


async def test_remediations_post_valid_returns_201_and_persists(api_client, db_session):
    sync = await _seed_sync_with_files(db_session)

    response = await api_client.post(
        REMEDIATIONS_URL,
        json={
            "sincronizacion_id": str(sync.id),
            "accion_ejecutada": "RETRY_JOB",
            "ejecutado_por": "j.medina",
            "resultado": "success",
            "notas": "reintento manual tras revisión",
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["accion_ejecutada"] == "RETRY_JOB"
    assert created["ejecutado_por"] == "j.medina"

    rows = (await api_client.get(REMEDIATIONS_URL)).json()
    assert any(row["id"] == created["id"] for row in rows)


async def test_remediations_post_unknown_accion_returns_422_no_row(api_client, db_session):
    sync = await _seed_sync_with_files(db_session)
    before = await db_session.scalar(select(func.count()).select_from(AccionRemediacion))

    response = await api_client.post(
        REMEDIATIONS_URL,
        json={"sincronizacion_id": str(sync.id), "accion_ejecutada": "UNKNOWN_ACTION",
              "ejecutado_por": "j.medina", "resultado": "success"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["codigo"] == "ERR_VALIDATION"

    after = await db_session.scalar(select(func.count()).select_from(AccionRemediacion))
    assert after == before  # no row persisted


async def test_remediations_post_missing_ejecutado_por_returns_422(api_client, db_session):
    sync = await _seed_sync_with_files(db_session)

    response = await api_client.post(
        REMEDIATIONS_URL,
        json={"sincronizacion_id": str(sync.id), "accion_ejecutada": "RETRY_JOB", "resultado": "success"},
    )
    assert response.status_code == 422


async def test_remediations_post_unknown_sync_returns_404(api_client, db_session):
    response = await api_client.post(
        REMEDIATIONS_URL,
        json={"sincronizacion_id": str(uuid.uuid4()), "accion_ejecutada": "RETRY_JOB",
              "ejecutado_por": "j.medina", "resultado": "success"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["codigo"] == "ERR_NOT_FOUND"


async def test_remediate_retry_job_transitions_failed_to_running(api_client, db_session):
    sync = await _seed_sync_with_files(db_session, estado=SyncEstado.failed, rejected=2)

    response = await api_client.post(f"{SYNCS_URL}/{sync.id}/remediate", json={"accion": "RETRY_JOB"})
    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == str(sync.id)
    assert updated["estado"] == "running"

    sync_id = sync.id
    db_session.expire_all()  # API mutated the row on another connection
    stored = await db_session.get(Sincronizacion, sync_id)
    assert stored.estado == SyncEstado.running

    accion = (await db_session.execute(
        select(AccionRemediacion).where(AccionRemediacion.sincronizacion_id == sync.id)
    )).scalar_one()
    assert accion.accion_ejecutada == "RETRY_JOB"
    assert accion.ejecutado_por == "svc.autoheal"  # default when absent


async def test_remediate_force_skip_validation_accepts_rejected_files(api_client, db_session):
    sync = await _seed_sync_with_files(db_session, estado=SyncEstado.rejected, rejected=2, total=3)

    response = await api_client.post(
        f"{SYNCS_URL}/{sync.id}/remediate", json={"accion": "FORCE_SKIP_VALIDATION"}
    )
    assert response.status_code == 200

    sync_id = sync.id
    db_session.expire_all()  # API mutated rows on another connection
    estados = (await db_session.execute(
        select(ArchivoProcesado.estado).where(ArchivoProcesado.sincronizacion_id == sync_id)
    )).scalars().all()
    assert set(estados) == {ArchivoEstado.accepted}  # all 3 now accepted

    accion = (await db_session.execute(
        select(AccionRemediacion).where(AccionRemediacion.sincronizacion_id == sync_id)
    )).scalar_one()
    assert accion.accion_ejecutada == "FORCE_SKIP_VALIDATION"


async def test_remediate_unsupported_accion_returns_422(api_client, db_session):
    sync = await _seed_sync_with_files(db_session, estado=SyncEstado.failed)

    response = await api_client.post(f"{SYNCS_URL}/{sync.id}/remediate", json={"accion": "PURGE_ALL"})
    assert response.status_code == 422
    assert response.json()["error"]["codigo"] == "ERR_VALIDATION"


async def test_remediate_unknown_sync_returns_404(api_client, db_session):
    response = await api_client.post(
        f"{SYNCS_URL}/{uuid.uuid4()}/remediate", json={"accion": "RETRY_JOB"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["codigo"] == "ERR_NOT_FOUND"
