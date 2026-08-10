"""RED schema integration tests (T1.6) — testcontainers + ``alembic upgrade head``.

RED until T1.7 (migration ``0001_initial``) exists: on an empty database the
catalog assertions below fail.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import (
    AccionRemediacion,
    ArchivoProcesado,
    LogError,
    Sincronizacion,
)
from app.models.enums import ArchivoEstado, NivelError, Resultado, SyncEstado, TipoArchivo

TABLES = {"sincronizaciones", "archivos_procesados", "logs_errores", "acciones_remediacion"}


def _make_sync(**overrides) -> Sincronizacion:
    return Sincronizacion(
        correlation_id=overrides.get("correlation_id", uuid.uuid4()),
        fecha_ejecucion=overrides.get("fecha_ejecucion", date(2024, 6, 12)),
        estado=overrides.get("estado", SyncEstado.completed),
        iniciado_at=overrides.get("iniciado_at", datetime(2024, 6, 12, 6, 0, tzinfo=timezone.utc)),
        finalizado_at=overrides.get("finalizado_at"),
        usuario_origen=overrides.get("usuario_origen", "svc.batch.ops"),
    )


# --- catalog -----------------------------------------------------------------


async def test_catalog_has_4_tables(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
    assert TABLES <= {row[0] for row in rows}


async def test_sincronizaciones_columns(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name, is_nullable, data_type, udt_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'sincronizaciones'"
            )
        )
    cols = {row[0]: row for row in rows}
    assert set(cols) == {
        "id", "correlation_id", "fecha_ejecucion", "estado",
        "iniciado_at", "finalizado_at", "usuario_origen",
    }
    assert cols["id"][1] == "NO" and cols["id"][3] == "uuid"
    assert cols["finalizado_at"][1] == "YES"  # nullable
    assert cols["estado"][3] == "sync_estado"  # native enum


async def test_archivos_jsonb_nullable(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT is_nullable, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'archivos_procesados' "
                "AND column_name = 'datos_payload'"
            )
        )
    nullable, dtype = rows.one()
    assert dtype == "jsonb"
    assert nullable == "YES"


async def test_enums_created(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT typname FROM pg_type "
                "WHERE typname IN ('sync_estado','tipo_archivo','archivo_estado','nivel_error','resultado')"
            )
        )
    assert {row[0] for row in rows} == {
        "sync_estado", "tipo_archivo", "archivo_estado", "nivel_error", "resultado",
    }


async def test_unique_indexes_correlation_id_and_checksum(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexdef ILIKE '%UNIQUE%'"
            )
        )
    defs = {row[0]: row[1] for row in rows}
    assert "ix_sincronizaciones_correlation_id" in defs
    assert "correlation_id" in defs["ix_sincronizaciones_correlation_id"]
    assert "ix_archivos_procesados_checksum" in defs
    assert "checksum" in defs["ix_archivos_procesados_checksum"]


async def test_fks_ondelete_cascade(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT tc.table_name, kcu.column_name, ccu.table_name, rc.delete_rule "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON tc.constraint_name = ccu.constraint_name "
                "JOIN information_schema.referential_constraints rc "
                "  ON tc.constraint_name = rc.constraint_name "
                "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'"
            )
        )
    fks = {(row[0], row[1], row[2]): row[3] for row in rows}
    assert fks[("archivos_procesados", "sincronizacion_id", "sincronizaciones")] == "CASCADE"
    assert fks[("logs_errores", "correlation_id", "sincronizaciones")] == "CASCADE"
    assert fks[("acciones_remediacion", "sincronizacion_id", "sincronizaciones")] == "CASCADE"


async def test_composite_indexes(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'")
        )
    defs = {row[0]: row[1] for row in rows}
    assert "ix_sincronizaciones_estado_fecha_ejecucion" in defs
    assert "ix_archivos_procesados_sincronizacion_id_estado" in defs
    assert "ix_acciones_remediacion_sincronizacion_id_ejecutada_at" in defs
    assert "ix_logs_errores_correlation_id_creado_at" in defs
    assert "DESC" in defs["ix_logs_errores_correlation_id_creado_at"]


# --- behavioral (DB-level constraints) --------------------------------------


async def test_unique_checksum_rejects_duplicate_at_db_level(db_session):
    sync = _make_sync()
    db_session.add(sync)
    await db_session.flush()
    db_session.add(
        ArchivoProcesado(
            sincronizacion_id=sync.id, nombre_archivo="a.csv",
            tipo_archivo=TipoArchivo.ventas, checksum="c" * 64,
            estado=ArchivoEstado.accepted, registros_totales=1,
        )
    )
    await db_session.flush()
    db_session.add(
        ArchivoProcesado(
            sincronizacion_id=sync.id, nombre_archivo="b.csv",
            tipo_archivo=TipoArchivo.inventario, checksum="c" * 64,
            estado=ArchivoEstado.accepted,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_unique_correlation_id_rejects_duplicate(db_session):
    cid = uuid.uuid4()
    db_session.add(_make_sync(correlation_id=cid))
    await db_session.flush()
    db_session.add(_make_sync(correlation_id=cid))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_cascade_delete_removes_dependents(db_session):
    sync = _make_sync()
    db_session.add(sync)
    await db_session.flush()
    db_session.add_all(
        [
            ArchivoProcesado(
                sincronizacion_id=sync.id, nombre_archivo="a.csv",
                tipo_archivo=TipoArchivo.ventas, checksum="a" * 64,
                estado=ArchivoEstado.rejected,
            ),
            LogError(
                correlation_id=sync.correlation_id, servicio_responsable="API_Gateway",
                nivel_error=NivelError.error, codigo_error="ERR_CHECKSUM_MISMATCH",
                mensaje="mismatch",
            ),
            AccionRemediacion(
                sincronizacion_id=sync.id, accion_ejecutada="RETRY_JOB",
                ejecutado_por="svc.autoheal", resultado=Resultado.success,
            ),
        ]
    )
    await db_session.commit()
    await db_session.execute(text("DELETE FROM sincronizaciones WHERE id = :id"), {"id": sync.id})
    await db_session.commit()
    for table in ("archivos_procesados", "logs_errores", "acciones_remediacion"):
        count = await db_session.scalar(text(f"SELECT count(*) FROM {table}"))
        assert count == 0, f"{table} not cascaded"


async def test_defaults_applied_on_insert(db_session):
    sync = _make_sync(estado=None)  # no estado → server default pending
    db_session.add(sync)
    await db_session.flush()
    archivo = ArchivoProcesado(
        sincronizacion_id=sync.id, nombre_archivo="a.csv",
        tipo_archivo=TipoArchivo.ventas, checksum="d" * 64, estado=ArchivoEstado.accepted,
    )
    db_session.add(archivo)
    await db_session.flush()
    await db_session.refresh(sync)
    await db_session.refresh(archivo)
    assert sync.estado == SyncEstado.pending
    assert archivo.registros_totales == 0
    log = LogError(
        correlation_id=sync.correlation_id, servicio_responsable="API_Gateway",
        nivel_error=NivelError.warning, codigo_error="ERR_DUPLICATE_BATCH", mensaje="replay",
    )
    accion = AccionRemediacion(
        sincronizacion_id=sync.id, accion_ejecutada="RETRY_JOB",
        ejecutado_por="svc.autoheal", resultado=Resultado.success,
    )
    db_session.add_all([log, accion])
    await db_session.flush()
    assert log.creado_at is not None
    assert accion.ejecutada_at is not None


async def test_log_fk_requires_existing_sincronizacion(db_session):
    db_session.add(
        LogError(
            correlation_id=uuid.uuid4(), servicio_responsable="API_Gateway",
            nivel_error=NivelError.error, codigo_error="ERR_JSON_MALFORMED", mensaje="bad",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_keyset_cursor_monotonicity(db_session):
    sync = _make_sync()
    db_session.add(sync)
    await db_session.flush()
    for i in range(5):
        db_session.add(
            LogError(
                correlation_id=sync.correlation_id, servicio_responsable="Data_Worker",
                nivel_error=NivelError.error, codigo_error="ERR_JSON_MALFORMED",
                mensaje=f"msg-{i}",
            )
        )
    await db_session.commit()
    ids = (await db_session.scalars(text("SELECT id FROM logs_errores ORDER BY id"))).all()
    assert len(ids) == 5
    first_page = (
        await db_session.scalars(text("SELECT id FROM logs_errores ORDER BY id DESC LIMIT 2"))
    ).all()
    assert first_page == [ids[4], ids[3]]
    second_page = (
        await db_session.scalars(
            text("SELECT id FROM logs_errores WHERE id < :cursor ORDER BY id DESC LIMIT 2"),
            {"cursor": first_page[-1]},
        )
    ).all()
    assert second_page == [ids[2], ids[1]]


# --- migration downgrade (data-model AC: downgrade removes all objects) ------


def test_downgrade_removes_all_objects(database_url):
    """Upgrade + downgrade on a scratch database (sync test — no running loop)."""
    import asyncio

    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.conftest import ALEMBIC_INI, BACKEND_ROOT, run_migrations

    base, _ = database_url.rsplit("/", 1)
    admin_url = f"{base}/postgres"
    scratch_url = f"{base}/scratch_mig"

    async def _prepare():
        admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text("DROP DATABASE IF EXISTS scratch_mig"))
            await conn.execute(text("CREATE DATABASE scratch_mig"))
        await admin.dispose()

    async def _catalog():
        engine = create_async_engine(scratch_url)
        async with engine.connect() as conn:
            tables = [
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
            ]
            types = [
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT typname FROM pg_type WHERE typname IN "
                        "('sync_estado','tipo_archivo','archivo_estado','nivel_error','resultado')"
                    )
                )
            ]
        await engine.dispose()
        return tables, types

    async def _cleanup():
        admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text("DROP DATABASE IF EXISTS scratch_mig"))
        await admin.dispose()

    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", scratch_url)

    asyncio.run(_prepare())
    run_migrations(scratch_url)
    tables, types = asyncio.run(_catalog())
    assert set(TABLES) <= set(tables)  # upgrade created all 4 business tables
    assert len(types) == 5
    alembic_command.downgrade(cfg, "base")
    tables, types = asyncio.run(_catalog())
    assert set(TABLES) & set(tables) == set()  # downgrade removed every business table
    assert types == []  # and every enum type
    asyncio.run(_cleanup())
