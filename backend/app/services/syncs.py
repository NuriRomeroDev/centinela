"""Syncs & remediations — server-side aggregates, N+1-free, remediation actions.

Spec: syncs-api, tasks.md T2.9.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AccionRemediacion, ArchivoProcesado, Sincronizacion
from app.models.enums import ArchivoEstado, Resultado, SyncEstado

REMEDIATION_ACTIONS = ("RETRY_JOB", "FORCE_SKIP_VALIDATION", "MANUAL_REQUEUE", "PURGE_DUPLICATE")
REMEDIATE_ACTIONS = ("RETRY_JOB", "FORCE_SKIP_VALIDATION")


async def list_syncs(session: AsyncSession, *, include_files: bool) -> list[dict]:
    """Syncs ordered iniciado_at DESC with server-side archivos_resumen.

    include_files=True embeds archivos (selectinload, no N+1); resumen computed
    from loaded files. include_files=False adds one GROUP BY for the resumen —
    either way a constant number of statements.
    """
    stmt = select(Sincronizacion).order_by(
        Sincronizacion.iniciado_at.desc(), Sincronizacion.id.desc()
    )
    if include_files:
        stmt = stmt.options(selectinload(Sincronizacion.archivos))
    syncs = (await session.execute(stmt)).scalars().all()

    if include_files:
        return [
            _sync_item(
                sync,
                (
                    len(sync.archivos),
                    sum(1 for f in sync.archivos if f.estado == ArchivoEstado.rejected),
                ),
                include_files=True,
            )
            for sync in syncs
        ]

    counts = (
        await session.execute(
            select(
                ArchivoProcesado.sincronizacion_id,
                func.count(),
                func.count().filter(ArchivoProcesado.estado == ArchivoEstado.rejected),
            )
            .where(ArchivoProcesado.sincronizacion_id.in_([s.id for s in syncs]))
            .group_by(ArchivoProcesado.sincronizacion_id)
        )
    ).all()
    resumen = {row[0]: (row[1], row[2]) for row in counts}
    return [_sync_item(sync, resumen.get(sync.id, (0, 0))) for sync in syncs]


def _sync_item(
    sync: Sincronizacion, resumen: tuple[int, int], *, include_files: bool = False
) -> dict:
    total, rejected = resumen
    item = {
        "id": str(sync.id),
        "correlation_id": str(sync.correlation_id),
        "estado": sync.estado.value if hasattr(sync.estado, "value") else str(sync.estado),
        "fecha_ejecucion": sync.fecha_ejecucion.isoformat(),
        "iniciado_at": sync.iniciado_at.isoformat(),
        "finalizado_at": sync.finalizado_at.isoformat() if sync.finalizado_at else None,
        "usuario_origen": sync.usuario_origen,
        "archivos_resumen": f"{total} total · {rejected} rechazados",
    }
    if include_files:
        item["archivos"] = [
            {
                "nombre_archivo": f.nombre_archivo,
                "tipo_archivo": (
                    f.tipo_archivo.value
                    if hasattr(f.tipo_archivo, "value")
                    else str(f.tipo_archivo)
                ),
                "checksum": f.checksum,
                "estado": f.estado.value if hasattr(f.estado, "value") else str(f.estado),
                "registros_totales": f.registros_totales,
            }
            for f in sorted(sync.archivos, key=lambda f: f.id)
        ]
    return item


async def _resumen_for(session: AsyncSession, sync: Sincronizacion) -> tuple[int, int]:
    total, rejected = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(ArchivoProcesado.estado == ArchivoEstado.rejected),
            ).where(ArchivoProcesado.sincronizacion_id == sync.id)
        )
    ).one()
    return total, rejected


async def list_remediations(session: AsyncSession) -> list[dict]:
    """Remediation history newest-first with correlation_id via selectinload join."""
    rows = (
        (
            await session.execute(
                select(AccionRemediacion)
                .options(selectinload(AccionRemediacion.sincronizacion))
                .order_by(AccionRemediacion.ejecutada_at.desc(), AccionRemediacion.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_accion_item(row) for row in rows]


def _accion_item(row: AccionRemediacion) -> dict:
    return {
        "id": row.id,
        "sincronizacion_id": str(row.sincronizacion_id),
        "correlation_id": str(row.sincronizacion.correlation_id) if row.sincronizacion else None,
        "accion_ejecutada": row.accion_ejecutada,
        "ejecutado_por": row.ejecutado_por,
        "resultado": row.resultado.value if hasattr(row.resultado, "value") else str(row.resultado),
        "notas": row.notas,
        "ejecutada_at": row.ejecutada_at.isoformat(),
    }


async def create_remediation(
    session: AsyncSession,
    *,
    sincronizacion_id: uuid.UUID,
    accion_ejecutada: str,
    ejecutado_por: str,
    resultado: str,
    notas: str | None = None,
) -> dict | None:
    """Persist a remediation history row; None when the sync is unknown."""
    sync = await session.get(Sincronizacion, sincronizacion_id)
    if sync is None:
        return None
    row = AccionRemediacion(
        sincronizacion_id=sync.id,
        accion_ejecutada=accion_ejecutada,
        ejecutado_por=ejecutado_por,
        resultado=Resultado(resultado),
        notas=notas,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    item = _accion_item(row)
    item["correlation_id"] = str(sync.correlation_id)
    return item


async def remediate(session: AsyncSession, *, sync_id: uuid.UUID, accion: str) -> dict | None:
    """Transition a sync per remediation action + persist history; None when unknown.

    RETRY_JOB: failed/rejected → running (re-processing). FORCE_SKIP_VALIDATION:
    rejected files → accepted. ejcutado_por defaults to svc.autoheal.
    """
    sync = await session.get(Sincronizacion, sync_id)
    if sync is None:
        return None

    if accion == "RETRY_JOB":
        sync.estado = SyncEstado.running
        sync.finalizado_at = None
    elif accion == "FORCE_SKIP_VALIDATION":
        files = (
            (
                await session.execute(
                    select(ArchivoProcesado).where(ArchivoProcesado.sincronizacion_id == sync.id)
                )
            )
            .scalars()
            .all()
        )
        for file in files:
            file.estado = ArchivoEstado.accepted
    else:
        raise ValueError(f"unsupported remediation action: {accion}")

    session.add(
        AccionRemediacion(
            sincronizacion_id=sync.id,
            accion_ejecutada=accion,
            ejecutado_por="svc.autoheal",
            resultado=Resultado.success,
        )
    )
    await session.commit()
    updated = await session.get(Sincronizacion, sync_id)
    return _sync_item(updated, await _resumen_for(session, updated))
