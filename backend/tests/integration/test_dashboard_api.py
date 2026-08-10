"""Dashboard API integration tests (T2.4, RED).

Scenarios (dashboard-api spec R1–R5, tasks.md T2.4):
- KPI metrics: correct aggregates on seeded data + zeros on empty dataset
- throughput: 7-day zero-fill, oldest→newest, days clamped 1–30
- status-distribution: 5 estados, counts sum, sorted desc, pct 1 decimal
- recent logs: newest-first, NO stack_trace, limit clamped 1–20
- N+1: constant (bounded) SQL query count on a 1,000-row dataset
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, insert, select

from app.db.seed import seed
from app.models import ArchivoProcesado, LogError, Sincronizacion
from app.models.enums import ArchivoEstado, NivelError, SyncEstado, TipoArchivo
from tests.integration.helpers import archivo_row, checksum, log_row, sync_row, utcnow

METRICS_URL = "/api/v1/dashboard/metrics"
THROUGHPUT_URL = "/api/v1/throughput"
STATUS_URL = "/api/v1/status-distribution"
RECENT_URL = "/api/v1/logs/recent"


async def _add_all(session, rows) -> None:
    session.add_all(rows)
    await session.commit()


async def test_metrics_on_seeded_data_matches_expected_aggregates(api_client, db_session):
    await seed(db_session)

    response = await api_client.get(METRICS_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["sincronizaciones_activas"] == 1  # seed has exactly one running sync
    assert body["completadas_hoy"] == 0  # seed dates are 2024-06-xx, not today
    assert body["archivos_rechazados"] == 6  # (i + j) % 5 == 0 across 31 files
    assert body["tasa_errores_criticos"] == "37.5"  # 3 CRITICAL / 8 logs


async def test_metrics_on_empty_dataset_returns_zeros(api_client):
    response = await api_client.get(METRICS_URL)

    assert response.status_code == 200
    assert response.json() == {
        "sincronizaciones_activas": 0,
        "completadas_hoy": 0,
        "archivos_rechazados": 0,
        "tasa_errores_criticos": "0.0",
    }


async def test_metrics_completadas_hoy_counts_today_only(api_client, db_session):
    today = date.today()
    completed_today = sync_row(estado=SyncEstado.completed, fecha=today)
    completed_other_day = sync_row(estado=SyncEstado.completed, fecha=today - timedelta(days=2))
    running_today = sync_row(estado=SyncEstado.running, fecha=today)
    await _add_all(db_session, [completed_today, completed_other_day, running_today])
    db_session.add_all([archivo_row(completed_today), archivo_row(running_today, estado=ArchivoEstado.rejected)])
    await db_session.commit()

    body = (await api_client.get(METRICS_URL)).json()
    assert body["sincronizaciones_activas"] == 1
    assert body["completadas_hoy"] == 1  # other-day completed sync NOT counted
    assert body["archivos_rechazados"] == 1


async def test_metrics_tasa_errores_criticos_is_one_decimal(api_client, db_session):
    syncs = [sync_row() for _ in range(2)]
    await _add_all(db_session, syncs)
    db_session.add_all(
        [log_row(syncs[0], codigo="ERR_JSON_MALFORMED", nivel=NivelError.critical),
         log_row(syncs[0], codigo="ERR_DB_TIMEOUT", nivel=NivelError.critical),
         log_row(syncs[0], codigo="ERR_NETWORK_RESET", nivel=NivelError.error),
         log_row(syncs[1], codigo="ERR_ORPHAN_RECORD", nivel=NivelError.error)]
    )
    await db_session.commit()

    body = (await api_client.get(METRICS_URL)).json()
    assert body["tasa_errores_criticos"] == "50.0"  # 2 CRITICAL / 4 logs


async def test_throughput_returns_7_entries_oldest_to_newest_with_zero_fill(api_client, db_session):
    today = date.today()
    # data on day 0 (today) and day 3; the other 5 days must be zero-filled
    sync_today = sync_row(fecha=today)
    sync_day3 = sync_row(fecha=today - timedelta(days=3))
    await _add_all(db_session, [sync_today, sync_day3])
    db_session.add_all(
        [
            archivo_row(sync_today),  # accepted
            archivo_row(sync_today),  # accepted
            archivo_row(sync_today, estado=ArchivoEstado.rejected),
            archivo_row(sync_day3),  # accepted
            archivo_row(sync_day3, estado=ArchivoEstado.rejected),
            archivo_row(sync_day3, estado=ArchivoEstado.rejected),
        ]
    )
    await db_session.commit()

    response = await api_client.get(THROUGHPUT_URL + "?days=7")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 7

    # oldest → newest
    dates = [entry["fecha"] for entry in entries]
    assert dates == sorted(dates)
    assert dates[0] == (today - timedelta(days=6)).isoformat()
    assert dates[-1] == today.isoformat()

    # sparse days are zero-filled; populated days carry correct counts
    by_day = {entry["fecha"]: entry for entry in entries}
    assert by_day[today.isoformat()] == {"fecha": today.isoformat(), "aceptados": 2, "rechazados": 1}
    assert by_day[(today - timedelta(days=3)).isoformat()] == {
        "fecha": (today - timedelta(days=3)).isoformat(),
        "aceptados": 1,
        "rechazados": 2,
    }
    empty_day = (today - timedelta(days=5)).isoformat()
    assert by_day[empty_day] == {"fecha": empty_day, "aceptados": 0, "rechazados": 0}


async def test_throughput_days_is_clamped_to_1_and_30(api_client, db_session):
    await _add_all(db_session, [sync_row()])  # one sync today

    below = (await api_client.get(THROUGHPUT_URL + "?days=0")).json()
    assert len(below) == 1  # clamped to 1

    above = (await api_client.get(THROUGHPUT_URL + "?days=999")).json()
    assert len(above) == 30  # clamped to 30


async def test_status_distribution_shape_counts_and_pct(api_client, db_session):
    rows = [
        sync_row(estado=SyncEstado.completed),
        sync_row(estado=SyncEstado.completed),
        sync_row(estado=SyncEstado.completed),
        sync_row(estado=SyncEstado.running),
        sync_row(estado=SyncEstado.running),
        sync_row(estado=SyncEstado.failed),
        sync_row(estado=SyncEstado.pending),
    ]
    await _add_all(db_session, rows)  # total 7; rejected absent → must still appear

    response = await api_client.get(STATUS_URL)
    assert response.status_code == 200
    items = response.json()

    assert len(items) == 5  # all 5 estados present
    by_estado = {item["estado"]: item for item in items}
    assert by_estado["completed"] == {"estado": "completed", "count": 3, "pct": "42.9"}
    assert by_estado["running"] == {"estado": "running", "count": 2, "pct": "28.6"}
    assert by_estado["failed"] == {"estado": "failed", "count": 1, "pct": "14.3"}
    assert by_estado["pending"] == {"estado": "pending", "count": 1, "pct": "14.3"}
    assert by_estado["rejected"] == {"estado": "rejected", "count": 0, "pct": "0.0"}

    counts = [item["count"] for item in items]
    assert counts == sorted(counts, reverse=True)  # sorted by count desc
    assert sum(counts) == 7  # sums to total syncs


async def test_recent_logs_returns_newest_first_without_stack_trace(api_client, db_session):
    sync = sync_row()
    await _add_all(db_session, [sync])
    base = utcnow()
    logs = [
        log_row(sync, codigo=f"ERR_{i}", nivel=NivelError.error, stack=f"trace-{i}", creado=base - timedelta(minutes=i))
        for i in range(8)
    ]
    db_session.add_all(logs)
    await db_session.commit()

    response = await api_client.get(RECENT_URL + "?limit=5")
    assert response.status_code == 200
    items = response.json()

    assert len(items) == 5
    assert [item["codigo_error"] for item in items] == [f"ERR_{i}" for i in range(5)]  # newest 5
    assert all("stack_trace" not in item for item in items)  # contract: no stack_trace
    assert set(items[0].keys()) == {
        "id", "correlation_id", "nivel_error", "codigo_error", "mensaje", "servicio_responsable", "creado_at",
    }


async def test_recent_logs_limit_is_clamped_to_1_and_20(api_client, db_session):
    sync = sync_row()
    await _add_all(db_session, [sync])
    db_session.add_all([log_row(sync, codigo=f"ERR_{i}") for i in range(30)])
    await db_session.commit()

    assert len((await api_client.get(RECENT_URL + "?limit=0")).json()) == 1  # clamped up to 1
    assert len((await api_client.get(RECENT_URL + "?limit=999")).json()) == 20  # clamped to 20
    assert len((await api_client.get(RECENT_URL)).json()) == 5  # default limit


async def test_dashboard_endpoints_are_n_plus_one_free_on_1000_rows(api_client, db_session, query_counter):
    ids = [f"11111111-2222-3333-4444-{i:012d}" for i in range(1000)]
    syncs = [
        {
            "id": ids[i],
            "correlation_id": f"aaaaaaaa-bbbb-cccc-dddd-{i:012d}",
            "fecha_ejecucion": date.today() - timedelta(days=i % 7),
            "estado": "completed",
            "iniciado_at": utcnow() - timedelta(hours=i),
            "finalizado_at": utcnow() - timedelta(hours=i - 1),
            "usuario_origen": "bulk",
        }
        for i in range(1000)
    ]
    archivos = [
        {
            "sincronizacion_id": ids[i],
            "nombre_archivo": f"bulk_{i}_{k}.csv",
            "tipo_archivo": "ventas",
            "checksum": checksum(f"bulk-{i}-{k}"),
            "estado": "accepted",
            "registros_totales": 5,
            "datos_payload": None,
        }
        for i in range(1000)
        for k in range(2)
    ]
    logs = [
        {
            "correlation_id": f"aaaaaaaa-bbbb-cccc-dddd-{i:012d}",
            "servicio_responsable": "DB_Connection_Pool",
            "nivel_error": "ERROR",
            "codigo_error": "ERR_DB_TIMEOUT",
            "mensaje": "bulk timeout",
            "stack_trace": None,
        }
        for i in range(1000)
    ]
    await db_session.execute(insert(Sincronizacion), syncs)
    await db_session.execute(insert(ArchivoProcesado), archivos)
    await db_session.execute(insert(LogError), logs)
    await db_session.commit()

    for url in (METRICS_URL, THROUGHPUT_URL + "?days=7", STATUS_URL, RECENT_URL + "?limit=20"):
        response = await api_client.get(url)
        assert response.status_code == 200

    # N+1 would blow past any sane bound; aggregates stay O(1) regardless of rows
    assert query_counter["statements"] < 40
