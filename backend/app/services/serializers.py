"""Shared API serializers — single source of truth for row → JSON shape."""

from __future__ import annotations

from app.models import LogError


def log_item(log: LogError) -> dict:
    """56px-row log columns (logs-api spec R1): NO stack_trace in list views."""
    return {
        "id": log.id,
        "correlation_id": str(log.correlation_id),
        "nivel_error": (
            log.nivel_error.value if hasattr(log.nivel_error, "value") else str(log.nivel_error)
        ),
        "codigo_error": log.codigo_error,
        "mensaje": log.mensaje,
        "servicio_responsable": log.servicio_responsable,
        "creado_at": log.creado_at.isoformat(),
    }
