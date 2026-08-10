"""Idempotent seed mirroring ``plantilla.html`` mock data (data-model spec Req 5).

Rerunnable: if ``sincronizaciones`` already has rows, seeding is skipped and the
current counts are returned (stable counts, no duplicates).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ChecksumMismatchError,
    DbUnavailableError,
    DuplicateBatchError,
    JsonMalformedError,
    NetworkResetError,
    OrphanRecordError,
    PoolExhaustedError,
    ValidationRejectedError,
)
from app.models import (
    AccionRemediacion,
    ArchivoProcesado,
    LogError,
    Sincronizacion,
)
from app.models.enums import ArchivoEstado, NivelError, Resultado, SyncEstado, TipoArchivo

SEED_NAMESPACE = uuid.UUID("6f0f2f0e-3f3a-4a1e-9c2b-5d6e7f8a9b0c")

SYNC_ESTADOS = (
    "completed",
    "completed",
    "running",
    "failed",
    "completed",
    "pending",
    "rejected",
    "completed",
)
TIPOS = (TipoArchivo.ventas, TipoArchivo.inventario, TipoArchivo.clientes)

LOG_DEFS: tuple[tuple[type[object], NivelError, str], ...] = (
    (ChecksumMismatchError, NivelError.error, "API_Gateway"),
    (DbUnavailableError, NivelError.critical, "DB_Connection_Pool"),
    (ValidationRejectedError, NivelError.warning, "Validation_Engine"),
    (DuplicateBatchError, NivelError.warning, "API_Gateway"),
    (NetworkResetError, NivelError.error, "Data_Worker"),
    (OrphanRecordError, NivelError.error, "Data_Worker"),
    (JsonMalformedError, NivelError.critical, "Validation_Engine"),
    (PoolExhaustedError, NivelError.critical, "DB_Connection_Pool"),
)

STACK_TRACES = {
    "ERR_CHECKSUM_MISMATCH": (
        'Traceback (most recent call last):\n  File "app/services/idempotency.py", line 88, '
        "in verify_checksum\n    raise ChecksumMismatchError(expected, actual)\n"
        "ingestion.exceptions.ChecksumMismatchError: expected=8f3a...c21 actual=1b7e...9f0"
    ),
    "ERR_POOL_EXHAUSTED": (
        'Traceback (most recent call last):\n  File "app/db/session.py", line 55, in acquire\n'
        '    raise PoolTimeout("no available connections")\n'
        "sqlalchemy.exc.TimeoutError: QueuePool limit of size 20 overflow 10 reached"
    ),
}

ACCIONES = ("RETRY_JOB", "FORCE_SKIP_VALIDATION", "MANUAL_REQUEUE", "PURGE_DUPLICATE")
NOTAS_ACCIONES = (
    "Reintento tras restablecer el pool de conexiones a PostgreSQL.",
    "Se omitió validación de esquema por acuerdo con Datos para lote histórico.",
    "Reencolado manual tras confirmar disponibilidad de servicio Data_Worker.",
    "Purga de registro duplicado detectado por control de checksum.",
)
ACTORES = ("n.romero", "a.rojas", "svc.autoheal")


@dataclass(frozen=True)
class SeedResult:
    """Outcome of a seed run."""

    skipped: bool
    counts: dict[str, int]


def _cid(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


def _checksum(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# Anchor: 2026-08-10 (Monday) — the week being demoed
_ANCHOR = date(2026, 8, 10)


def _ts(day_offset: int, hour: int, minute: int) -> datetime:
    d = _ANCHOR - __import__("datetime").timedelta(days=day_offset)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)


def _build_syncs() -> list[Sincronizacion]:
    syncs: list[Sincronizacion] = []
    for i, estado in enumerate(SYNC_ESTADOS):
        finalizado = None if estado in ("running", "pending") else _ts(i, 7, (i * 4 + 22) % 60)
        d = _ANCHOR - __import__("datetime").timedelta(days=i)
        syncs.append(
            Sincronizacion(
                correlation_id=_cid(f"sync-{i}"),
                fecha_ejecucion=d,
                estado=SyncEstado(estado),
                iniciado_at=_ts(i, 6, i * 4),
                finalizado_at=finalizado,
                usuario_origen="svc.batch.ops" if i % 2 == 0 else "n.romero",
            )
        )
    return syncs


_REJECTED_SYNC_INDICES = {
    i for i, estado in enumerate(SYNC_ESTADOS) if estado in ("rejected", "failed")
}


def _build_archivos(syncs: list[Sincronizacion]) -> list[ArchivoProcesado]:
    archivos: list[ArchivoProcesado] = []
    for i, sync in enumerate(syncs):
        for j in range(3 + i % 3):
            tipo = TIPOS[j % 3]
            rechazado = (i + j) % 5 == 0 or (i in _REJECTED_SYNC_INDICES and j == 0)
            registros = 1200 + i * 340 + j * 88
            d = _ANCHOR - __import__("datetime").timedelta(days=i)
            archivos.append(
                ArchivoProcesado(
                    sincronizacion_id=sync.id,
                    nombre_archivo=f"lote_{tipo.value}_{d.strftime('%Y%m%d')}_{j + 1:02d}.csv",
                    tipo_archivo=tipo,
                    checksum=_checksum(f"sync-{i}-file-{j}"),
                    estado=ArchivoEstado.rejected if rechazado else ArchivoEstado.accepted,
                    registros_totales=registros,
                    datos_payload=(
                        None
                        if rechazado
                        else {
                            "tipo": tipo.value,
                            "registros": registros,
                            "procesado_por": sync.usuario_origen,
                        }
                    ),
                )
            )
    return archivos


def _build_logs(syncs: list[Sincronizacion]) -> list[LogError]:
    logs: list[LogError] = []
    for i, (error_cls, nivel, servicio) in enumerate(LOG_DEFS):
        logs.append(
            LogError(
                correlation_id=syncs[i % len(syncs)].correlation_id,
                servicio_responsable=servicio,
                nivel_error=nivel,
                codigo_error=error_cls.codigo,  # type: ignore[attr-defined]
                mensaje=error_cls.mensaje_default,  # type: ignore[attr-defined]
                stack_trace=STACK_TRACES.get(error_cls.codigo),  # type: ignore[attr-defined]
                creado_at=_ts(i % 7, 8 + (i % 10), (i * 11) % 60),
            )
        )
    return logs


def _build_acciones(syncs: list[Sincronizacion]) -> list[AccionRemediacion]:
    acciones: list[AccionRemediacion] = []
    for i in range(9):
        acciones.append(
            AccionRemediacion(
                sincronizacion_id=syncs[i % len(syncs)].id,
                accion_ejecutada=ACCIONES[i % len(ACCIONES)],
                ejecutado_por=ACTORES[i % len(ACTORES)],
                resultado=Resultado.failed if i % 4 == 3 else Resultado.success,
                notas=NOTAS_ACCIONES[i % len(NOTAS_ACCIONES)],
                ejecutada_at=_ts(i % 7, 9 + (i % 6), (i * 17) % 60),
            )
        )
    return acciones


async def _counts(session: AsyncSession) -> dict[str, int]:
    return {
        "sincronizaciones": await session.scalar(select(func.count()).select_from(Sincronizacion)),
        "archivos_procesados": await session.scalar(
            select(func.count()).select_from(ArchivoProcesado)
        ),
        "logs_errores": await session.scalar(select(func.count()).select_from(LogError)),
        "acciones_remediacion": await session.scalar(
            select(func.count()).select_from(AccionRemediacion)
        ),
    }


async def seed(session: AsyncSession) -> SeedResult:
    """Insert the plantilla-mirroring dataset; skip (idempotent) if data exists."""
    existing = await session.scalar(select(func.count()).select_from(Sincronizacion))
    if existing:
        return SeedResult(skipped=True, counts=await _counts(session))

    syncs = _build_syncs()
    session.add_all(syncs)
    await session.flush()
    session.add_all(_build_archivos(syncs) + _build_logs(syncs) + _build_acciones(syncs))
    await session.commit()
    return SeedResult(skipped=False, counts=await _counts(session))


def main() -> None:
    """CLI entry point: ``python -m app.db.seed`` (uses ``DATABASE_URL`` from env)."""
    import asyncio

    from app.db.session import get_session_factory

    async def _run() -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await seed(session)
        print(f"seed {'skipped (data exists)' if result.skipped else 'applied'}: {result.counts}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
