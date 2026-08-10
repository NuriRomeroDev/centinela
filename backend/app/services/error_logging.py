"""Best-effort structured error log persistence (corruption-handling spec R1/R3, design §4.8).

The global exception handlers append a ``logs_errores`` row in a FRESH
transaction tied to ``correlation_id``. Because ``logs_errores.correlation_id``
references ``sincronizaciones.correlation_id``, a failed sync parent is created
when none exists (a corrupt ingest never produces a *success* record). Any
failure — e.g. DB outage — is swallowed: the error is surfaced via HTTP only
("persisted (or surfaced)" per corruption-handling spec R3).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import LogError, Sincronizacion
from app.models.enums import NivelError, SyncEstado

logger = logging.getLogger(__name__)

# codigo → (nivel_error, servicio_responsable) — mirrors seed LOG_DEFS (BE8).
ERROR_LOG_META: dict[str, tuple[NivelError, str]] = {
    "ERR_CHECKSUM_MISMATCH": (NivelError.error, "API_Gateway"),
    "ERR_DB_TIMEOUT": (NivelError.critical, "DB_Connection_Pool"),
    "ERR_SCHEMA_VALIDATION": (NivelError.warning, "Validation_Engine"),
    "ERR_DUPLICATE_BATCH": (NivelError.warning, "API_Gateway"),
    "ERR_NETWORK_RESET": (NivelError.error, "Data_Worker"),
    "ERR_ORPHAN_RECORD": (NivelError.error, "Data_Worker"),
    "ERR_JSON_MALFORMED": (NivelError.critical, "Validation_Engine"),
    "ERR_POOL_EXHAUSTED": (NivelError.critical, "DB_Connection_Pool"),
}

FALLBACK_META = (NivelError.error, "API_Gateway")


async def persist_error_log(
    factory: async_sessionmaker,
    *,
    correlation_id: str,
    codigo: str,
    mensaje: str,
    stack_trace: str | None = None,
) -> None:
    """Persist a structured log row best-effort; never raises."""
    try:
        cid = uuid.UUID(str(correlation_id))
    except (ValueError, TypeError):
        logger.warning("skipping error log without valid correlation_id (codigo=%s)", codigo)
        return

    nivel, servicio = ERROR_LOG_META.get(codigo, FALLBACK_META)
    try:
        async with factory() as session:
            parent = await session.scalar(
                select(Sincronizacion.id).where(Sincronizacion.correlation_id == cid)
            )
            if parent is None:
                session.add(
                    Sincronizacion(
                        correlation_id=cid,
                        fecha_ejecucion=date.today(),
                        estado=SyncEstado.failed,
                        iniciado_at=datetime.now(timezone.utc),
                        usuario_origen="svc.ingest",
                    )
                )
            session.add(
                LogError(
                    correlation_id=cid,
                    servicio_responsable=servicio,
                    nivel_error=nivel,
                    codigo_error=codigo,
                    mensaje=mensaje,
                    stack_trace=stack_trace,
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — DB down etc.; surfaced via HTTP instead
        logger.exception(
            "failed to persist error log (codigo=%s correlation_id=%s)", codigo, correlation_id
        )
