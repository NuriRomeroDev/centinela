"""Centinela error taxonomy.

Every backend failure is an :class:`AppError` subclass carrying an HTTP status
code and a stable machine-readable error code (the 8 seed codes from design
§4.8). Handlers (Batch 2) map these to ``{error: {codigo, mensaje,
correlation_id}}`` responses.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all Centinela application errors."""

    status_code: int = 500
    codigo: str = "ERR_INTERNAL"
    mensaje_default: str = "Internal server error."

    def __init__(self, mensaje: str | None = None, *, correlation_id: str | None = None):
        self.mensaje = mensaje or self.mensaje_default
        self.correlation_id = correlation_id
        super().__init__(self.mensaje)

    def to_body(self) -> dict[str, Any]:
        """Structured error body per spec: ``{error: {codigo, mensaje, correlation_id}}``."""
        return {
            "error": {
                "codigo": self.codigo,
                "mensaje": self.mensaje,
                "correlation_id": self.correlation_id,
            }
        }


class ChecksumMismatchError(AppError):
    """Computed SHA-256 differs from the client-supplied ``X-Checksum-SHA256``."""

    status_code = 422
    codigo = "ERR_CHECKSUM_MISMATCH"
    mensaje_default = "El checksum SHA-256 del archivo no coincide con el payload recibido."


class DbUnavailableError(AppError):
    """Connection acquisition timed out; PostgreSQL unreachable."""

    status_code = 503
    codigo = "ERR_DB_TIMEOUT"
    mensaje_default = "Tiempo de espera agotado al conectar con PostgreSQL."


class ValidationRejectedError(AppError):
    """Payload record failed schema validation."""

    status_code = 422
    codigo = "ERR_SCHEMA_VALIDATION"
    mensaje_default = "El registro no cumple con el esquema esperado."


class DuplicateBatchError(AppError):
    """Replay of an already-ingested correlation_id — idempotent original result."""

    status_code = 200
    codigo = "ERR_DUPLICATE_BATCH"
    mensaje_default = "Lote reenviado detectado; se retornó el resultado idempotente original."


class NetworkResetError(AppError):
    """Peer reset the connection mid-stream; body truncated."""

    status_code = 422
    codigo = "ERR_NETWORK_RESET"
    mensaje_default = "La conexión fue reiniciada por el peer durante la transmisión del lote."


class OrphanRecordError(AppError):
    """Row without its parent synchronization (FK violation)."""

    status_code = 422
    codigo = "ERR_ORPHAN_RECORD"
    mensaje_default = "Registro huérfano sin sincronización asociada."


class JsonMalformedError(AppError):
    """JSONB payload could not be deserialized."""

    status_code = 422
    codigo = "ERR_JSON_MALFORMED"
    mensaje_default = "El payload JSONB no pudo ser deserializado."


class PoolExhaustedError(AppError):
    """Connection pool exhausted after bounded retries."""

    status_code = 503
    codigo = "ERR_POOL_EXHAUSTED"
    mensaje_default = "Pool de conexiones agotado bajo alta concurrencia."


ERROR_CLASSES: tuple[type[AppError], ...] = (
    ChecksumMismatchError,
    DbUnavailableError,
    ValidationRejectedError,
    DuplicateBatchError,
    NetworkResetError,
    OrphanRecordError,
    JsonMalformedError,
    PoolExhaustedError,
)

ERROR_CODES: tuple[str, ...] = tuple(cls.codigo for cls in ERROR_CLASSES)

ERROR_HTTP_STATUS: dict[str, int] = {cls.codigo: cls.status_code for cls in ERROR_CLASSES}


def http_status_for(codigo: str) -> int:
    """Return the HTTP status mapped to an error code (KeyError for unknown codes)."""
    return ERROR_HTTP_STATUS[codigo]
