"""Logs read endpoints (tasks.md T2.6): keyset pagination, search, detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.logs import DEFAULT_PAGE_SIZE, list_logs, log_detail

router = APIRouter(tags=["logs"])


@router.get("/logs")
async def logs_list(
    cursor: int | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = None,
    mensaje: str | None = None,
    codigo_error: str | None = None,
    servicio_responsable: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Paginated error logs: keyset (cursor) or offset (page/page_size), filters AND-composed."""
    return await list_logs(
        session,
        cursor=cursor,
        page=page,
        page_size=page_size,
        search=search,
        mensaje=mensaje,
        codigo_error=codigo_error,
        servicio_responsable=servicio_responsable,
    )


@router.get("/logs/{log_id}")
async def logs_detail(log_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Full log row incl. stack_trace."""
    item = await log_detail(session, log_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Log no encontrado.")
    return item
