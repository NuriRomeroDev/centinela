"""Dashboard read endpoints (design §4.7): metrics, throughput, status distribution, recent logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.metrics import metrics, recent_logs, status_distribution, throughput

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/metrics")
async def dashboard_metrics(session: AsyncSession = Depends(get_session)) -> dict:
    """KPI metrics: activas, completadas_hoy, archivos_rechazados, tasa críticos."""
    return await metrics(session)


@router.get("/throughput")
async def throughput_endpoint(days: int = 7, session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Per-day accepted/rejected files, zero-filled, days clamped 1–30."""
    return await throughput(session, days)


@router.get("/status-distribution")
async def status_distribution_endpoint(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Per-estado distribution over the 5 estados, sorted count desc."""
    return await status_distribution(session)


@router.get("/logs/recent")
async def logs_recent(limit: int = 5, session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Newest error logs (no stack_trace), limit clamped 1–20."""
    return await recent_logs(session, limit)
