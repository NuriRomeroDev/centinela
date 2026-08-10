"""Idempotent ingest persistence (design §4.4) — TOCTOU-safe.

Two-layered duplicate detection:
1. pre-check ``SELECT`` on ``sincronizaciones.correlation_id`` → replay 200.
2. ``IntegrityError`` on the unique ``checksum``/``correlation_id`` constraint
   under concurrency → the loser loads the winner's original row → replay 200.

Both duplicate paths append a ``ERR_DUPLICATE_BATCH`` WARNING log row (fresh
session, tied to the ORIGINAL sync's correlation_id) and never create a second
archivo row.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.errors import DuplicateBatchError
from app.models import ArchivoProcesado, LogError, Sincronizacion
from app.models.enums import ArchivoEstado, NivelError, SyncEstado, TipoArchivo

SERVICE_ORIGIN = "svc.ingest"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _response_dict(sync: Sincronizacion, archivo: ArchivoProcesado) -> dict:
    """Stored payload echoed by 201 (and the identical 200 replay)."""
    return {
        "correlation_id": str(sync.correlation_id),
        "sync_id": str(sync.id),
        "estado": sync.estado.value if hasattr(sync.estado, "value") else str(sync.estado),
        "nombre_archivo": archivo.nombre_archivo,
        "tipo_archivo": archivo.tipo_archivo.value if hasattr(archivo.tipo_archivo, "value") else str(archivo.tipo_archivo),
        "checksum": archivo.checksum,
        "registros_totales": archivo.registros_totales,
    }


async def _load_original(
    factory: async_sessionmaker[AsyncSession],
    *,
    correlation_id: uuid.UUID | None = None,
    checksum: str | None = None,
) -> Sincronizacion | None:
    """Load the committed original sync (with files) by correlation_id, then checksum."""
    async with factory() as session:
        stmt = select(Sincronizacion).options(selectinload(Sincronizacion.archivos))
        if correlation_id is not None:
            stmt = stmt.where(Sincronizacion.correlation_id == correlation_id)
            sync = await session.scalar(stmt)
            if sync is not None:
                return sync
        if checksum is not None:
            stmt = (
                select(Sincronizacion)
                .options(selectinload(Sincronizacion.archivos))
                .where(Sincronizacion.archivos.any(ArchivoProcesado.checksum == checksum))
            )
            return await session.scalar(stmt)
        return None


async def _persist_duplicate_log(factory: async_sessionmaker[AsyncSession], cid: uuid.UUID) -> None:
    """Append the ERR_DUPLICATE_BATCH WARNING row (own transaction, FK-safe)."""
    async with factory() as session:
        session.add(
            LogError(
                correlation_id=cid,
                servicio_responsable="API_Gateway",
                nivel_error=NivelError.warning,
                codigo_error=DuplicateBatchError.codigo,
                mensaje=DuplicateBatchError.mensaje_default,
            )
        )
        await session.commit()


async def ingest_batch(
    session: AsyncSession,
    factory: async_sessionmaker[AsyncSession],
    *,
    correlation_id: uuid.UUID,
    file_name: str,
    tipo_archivo: TipoArchivo,
    checksum: str,
    payload: list[dict],
) -> tuple[int, dict]:
    """Persist sync + archivo + JSONB payload in ONE transaction.

    Returns ``(status_code, response_dict)``: 201 on first ingest, 200 with the
    identical stored payload on replay (pre-check or IntegrityError race).
    """
    existing = await session.scalar(
        select(Sincronizacion)
        .where(Sincronizacion.correlation_id == correlation_id)
        .options(selectinload(Sincronizacion.archivos))
    )
    if existing and existing.archivos:
        # pre-check hit → idempotent replay of the ORIGINAL result
        await _persist_duplicate_log(factory, existing.correlation_id)
        return 200, _response_dict(existing, existing.archivos[0])

    # Reuse a previous FAILED attempt's sync (corrupt payload, same cid) —
    # unique(correlation_id) forbids a second row; its logs stay intact.
    sync = existing or Sincronizacion(correlation_id=correlation_id)
    sync.fecha_ejecucion = date.today()
    sync.estado = SyncEstado.completed
    sync.iniciado_at = _now()
    sync.finalizado_at = _now()
    sync.usuario_origen = SERVICE_ORIGIN

    archivo = ArchivoProcesado(
        sincronizacion=sync,
        nombre_archivo=file_name,
        tipo_archivo=tipo_archivo,
        checksum=checksum,
        estado=ArchivoEstado.accepted,
        registros_totales=len(payload),
        datos_payload={
            "registros": len(payload),
            "tipo": tipo_archivo.value,
            "procesado_por": SERVICE_ORIGIN,
        },
    )
    session.add(sync)
    session.add(archivo)
    try:
        await session.commit()
    except IntegrityError:
        # TOCTOU: another request committed first (same correlation_id or same
        # unique checksum) → treat as duplicate, return the original.
        await session.rollback()
        original = await _load_original(
            factory, correlation_id=correlation_id, checksum=checksum
        )
        if original is None or not original.archivos:
            raise
        await _persist_duplicate_log(factory, original.correlation_id)
        return 200, _response_dict(original, original.archivos[0])

    return 201, _response_dict(sync, archivo)
