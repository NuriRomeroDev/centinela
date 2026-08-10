"""Logs API — keyset pagination (logs-api spec R1–R4, tasks.md T2.6).

Keyset (cursor) is the primary path: id < cursor, newest-first, page_size+1
lookahead → O(1) statements per page, stable under inserts. Offset paging
(page/page_size) kept for footer pages / jump-to-page. Search and per-field
filters compose with both paths (AND) via ILIKE contains, case-insensitive.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LogError
from app.services.serializers import log_item

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _filters(
    search: str | None,
    mensaje: str | None,
    codigo_error: str | None,
    servicio_responsable: str | None,
) -> list:
    filters = []
    if search:
        like = f"%{search}%"
        filters.append(
            or_(
                LogError.mensaje.ilike(like),
                LogError.codigo_error.ilike(like),
                LogError.servicio_responsable.ilike(like),
            )
        )
    if mensaje:
        filters.append(LogError.mensaje.ilike(f"%{mensaje}%"))
    if codigo_error:
        filters.append(LogError.codigo_error.ilike(f"%{codigo_error}%"))
    if servicio_responsable:
        filters.append(LogError.servicio_responsable.ilike(f"%{servicio_responsable}%"))
    return filters


async def list_logs(
    session: AsyncSession,
    *,
    cursor: int | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = None,
    mensaje: str | None = None,
    codigo_error: str | None = None,
    servicio_responsable: str | None = None,
) -> dict:
    """Paginated logs list. Returns {items, total, next_cursor, page_size, page}."""
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    filters = _filters(search, mensaje, codigo_error, servicio_responsable)

    total = await session.scalar(select(func.count()).select_from(LogError).where(*filters)) or 0

    stmt = select(LogError).where(*filters).order_by(LogError.id.desc())
    if cursor is not None:
        rows = (
            (await session.execute(stmt.where(LogError.id < cursor).limit(page_size + 1)))
            .scalars()
            .all()
        )
        items = rows[:page_size]
        # lookahead row proves more exist; cursor = last RETURNED id so no row is dropped
        next_cursor = items[-1].id if len(rows) > page_size else None
    else:
        page = max(page, 1)
        items = (
            (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size)))
            .scalars()
            .all()
        )
        next_cursor = items[-1].id if (page * page_size) < total else None

    return {
        "items": [log_item(log) for log in items],
        "total": total,
        "next_cursor": next_cursor,
        "page_size": page_size,
        "page": page,
    }


async def log_detail(session: AsyncSession, log_id: int) -> dict | None:
    """Full log row incl. stack_trace, or None when unknown."""
    log = await session.get(LogError, log_id)
    if log is None:
        return None
    return {**log_item(log), "stack_trace": log.stack_trace}
