"""Dashboard aggregates — SQL aggregates only, no full-table loads (design §4.6, BE5).

N+1-free by construction: every endpoint issues a constant number of aggregate
statements regardless of row count (enforced by query-count integration tests).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArchivoProcesado, LogError, Sincronizacion
from app.models.enums import ArchivoEstado, NivelError, SyncEstado
from app.services.serializers import log_item

SYNC_ESTADOS: tuple[SyncEstado, ...] = tuple(SyncEstado)


async def metrics(session: AsyncSession) -> dict:
    """KPI metrics (dashboard-api spec R1); zeros on empty dataset."""
    activas = await session.scalar(
        select(func.count()).select_from(Sincronizacion).where(Sincronizacion.estado == SyncEstado.running)
    )
    completadas_hoy = await session.scalar(
        select(func.count())
        .select_from(Sincronizacion)
        .where(Sincronizacion.estado == SyncEstado.completed, Sincronizacion.fecha_ejecucion == date.today())
    )
    rechazados = await session.scalar(
        select(func.count()).select_from(ArchivoProcesado).where(ArchivoProcesado.estado == ArchivoEstado.rejected)
    )
    total_logs = await session.scalar(select(func.count()).select_from(LogError))
    criticos = await session.scalar(
        select(func.count()).select_from(LogError).where(LogError.nivel_error == NivelError.critical)
    )
    tasa = (criticos / total_logs * 100) if total_logs else 0.0
    return {
        "sincronizaciones_activas": activas or 0,
        "completadas_hoy": completadas_hoy or 0,
        "archivos_rechazados": rechazados or 0,
        "tasa_errores_criticos": f"{tasa:.1f}",
    }


async def throughput(session: AsyncSession, days: int) -> list[dict]:
    """Per-day accepted/rejected file counts for the last ``days`` (clamped 1–30).

    One GROUP BY query + Python zero-fill for sparse days, oldest→newest.
    """
    days = min(max(days, 1), 30)
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(
                Sincronizacion.fecha_ejecucion,
                func.count().filter(ArchivoProcesado.estado == ArchivoEstado.accepted),
                func.count().filter(ArchivoProcesado.estado == ArchivoEstado.rejected),
            )
            .join(ArchivoProcesado, ArchivoProcesado.sincronizacion_id == Sincronizacion.id)
            .where(Sincronizacion.fecha_ejecucion >= start)
            .group_by(Sincronizacion.fecha_ejecucion)
        )
    ).all()
    by_day = {row[0]: (row[1], row[2]) for row in rows}
    return [
        {
            "fecha": day.isoformat(),
            "aceptados": by_day.get(day, (0, 0))[0],
            "rechazados": by_day.get(day, (0, 0))[1],
        }
        for day in (start + timedelta(days=i) for i in range(days))
    ]


async def status_distribution(session: AsyncSession) -> list[dict]:
    """Per-estado {estado, count, pct} over the 5 estados, count desc, pct 1 dp."""
    rows = (await session.execute(select(Sincronizacion.estado, func.count()).group_by(Sincronizacion.estado))).all()
    counts = {estado: count for estado, count in rows}
    total = sum(counts.values())
    items = [
        {
            "estado": estado.value,
            "count": counts.get(estado, 0),
            "pct": f"{(counts.get(estado, 0) / total * 100):.1f}" if total else "0.0",
        }
        for estado in SYNC_ESTADOS
    ]
    items.sort(key=lambda item: item["count"], reverse=True)
    return items


async def recent_logs(session: AsyncSession, limit: int) -> list[dict]:
    """Newest logs (creado_at DESC, id DESC), NO stack_trace, limit clamped 1–20."""
    limit = min(max(limit, 1), 20)
    rows = (
        (await session.execute(select(LogError).order_by(LogError.creado_at.desc(), LogError.id.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return [log_item(log) for log in rows]
