"""Seed integration tests (T1.8) — mirrors plantilla.html, idempotent, stable counts.

RED phase: references ``app.db.seed`` which does not exist yet.
"""

from sqlalchemy import func, select

from app.core.errors import ERROR_CODES
from app.db.seed import seed
from app.models import (
    AccionRemediacion,
    ArchivoProcesado,
    LogError,
    Sincronizacion,
)
from app.models.enums import ArchivoEstado, NivelError, Resultado, SyncEstado, TipoArchivo

EXPECTED_COUNTS = {
    "sincronizaciones": 8,
    "archivos_procesados": 31,
    "logs_errores": 8,
    "acciones_remediacion": 9,
}

SERVICIOS = {"API_Gateway", "Validation_Engine", "Data_Worker", "DB_Connection_Pool"}
ACCIONES = {"RETRY_JOB", "FORCE_SKIP_VALIDATION", "MANUAL_REQUEUE", "PURGE_DUPLICATE"}


async def _table_counts(session) -> dict[str, int]:
    return {
        "sincronizaciones": await session.scalar(select(func.count()).select_from(Sincronizacion)),
        "archivos_procesados": await session.scalar(select(func.count()).select_from(ArchivoProcesado)),
        "logs_errores": await session.scalar(select(func.count()).select_from(LogError)),
        "acciones_remediacion": await session.scalar(select(func.count()).select_from(AccionRemediacion)),
    }


async def test_seed_creates_expected_row_counts(db_session):
    result = await seed(db_session)
    assert result.skipped is False
    assert result.counts == EXPECTED_COUNTS


async def test_seed_is_idempotent_and_rerunnable(db_session):
    first = await seed(db_session)
    second = await seed(db_session)
    assert second.skipped is True  # second run detected existing rows
    assert second.counts == first.counts == EXPECTED_COUNTS


async def test_seed_parity_mirrors_plantilla(db_session):
    await seed(db_session)
    estados = set((await db_session.scalars(select(Sincronizacion.estado).distinct())).all())
    assert estados == set(SyncEstado)  # all 5 estados
    tipos = set((await db_session.scalars(select(ArchivoProcesado.tipo_archivo).distinct())).all())
    assert tipos == set(TipoArchivo)  # all 3 tipo_archivo
    codigos = set((await db_session.scalars(select(LogError.codigo_error).distinct())).all())
    assert codigos == set(ERROR_CODES)  # all 8 error codes
    niveles = set((await db_session.scalars(select(LogError.nivel_error).distinct())).all())
    assert niveles == {NivelError.warning, NivelError.error, NivelError.critical}
    servicios = set((await db_session.scalars(select(LogError.servicio_responsable).distinct())).all())
    assert servicios == SERVICIOS
    acciones = set((await db_session.scalars(select(AccionRemediacion.accion_ejecutada).distinct())).all())
    assert acciones == ACCIONES
    resultados = set((await db_session.scalars(select(AccionRemediacion.resultado).distinct())).all())
    assert resultados == {Resultado.success, Resultado.failed}


async def test_seed_checksums_are_unique_and_64_hex(db_session):
    await seed(db_session)
    checksums = (await db_session.scalars(select(ArchivoProcesado.checksum))).all()
    assert len(checksums) == EXPECTED_COUNTS["archivos_procesados"]
    assert len(set(checksums)) == len(checksums)  # unique (idempotency guard)
    assert all(len(c) == 64 and all(ch in "0123456789abcdef" for ch in c) for c in checksums)


async def test_seed_has_rejected_files_and_remediations(db_session):
    await seed(db_session)
    rejected = await db_session.scalar(
        select(func.count()).select_from(ArchivoProcesado).where(ArchivoProcesado.estado == ArchivoEstado.rejected)
    )
    assert rejected and rejected > 0  # rejected files KPI has content
    remediaciones = await db_session.scalar(select(func.count()).select_from(AccionRemediacion))
    assert remediaciones >= 4
