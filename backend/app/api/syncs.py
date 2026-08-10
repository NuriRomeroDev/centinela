"""Syncs + remediations endpoints (tasks.md T2.9): list with files, history, record, remediate."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.syncs import create_remediation, list_remediations, list_syncs, remediate

router = APIRouter(tags=["syncs"])


@router.get("/syncs")
async def syncs_list(
    include_files: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Syncs iniciado_at DESC with server-side archivos_resumen; embed files optionally."""
    return await list_syncs(session, include_files=include_files)


@router.get("/remediations")
async def remediations_list(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Remediation history newest-first (correlation_id via join)."""
    return await list_remediations(session)


class RemediationIn(BaseModel):
    sincronizacion_id: uuid.UUID
    accion_ejecutada: Literal[
        "RETRY_JOB", "FORCE_SKIP_VALIDATION", "MANUAL_REQUEUE", "PURGE_DUPLICATE"
    ]
    ejecutado_por: str
    resultado: Literal["success", "failed"]
    notas: str | None = None


@router.post("/remediations", status_code=201)
async def remediations_post(
    payload: RemediationIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Record a remediation history row (422 unknown accion/fields, 404 unknown sync)."""
    item = await create_remediation(session, **payload.model_dump())
    if item is None:
        raise HTTPException(status_code=404, detail="Sincronización no encontrada.")
    return item


class RemediateIn(BaseModel):
    accion: Literal["RETRY_JOB", "FORCE_SKIP_VALIDATION"]


@router.post("/syncs/{sync_id}/remediate")
async def sync_remediate(
    sync_id: uuid.UUID,
    payload: RemediateIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Transition the sync (RETRY_JOB → running; FORCE_SKIP_VALIDATION → files accepted)."""
    item = await remediate(session, sync_id=sync_id, accion=payload.accion)
    if item is None:
        raise HTTPException(status_code=404, detail="Sincronización no encontrada.")
    return item
