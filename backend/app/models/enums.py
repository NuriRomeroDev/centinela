"""Enum types shared by the ORM models (data-model spec)."""

import enum


class SyncEstado(str, enum.Enum):
    """Estado de sincronización: pending | running | completed | failed | rejected."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    rejected = "rejected"


class TipoArchivo(str, enum.Enum):
    """Tipo de archivo: ventas | inventario | clientes."""

    ventas = "ventas"
    inventario = "inventario"
    clientes = "clientes"


class ArchivoEstado(str, enum.Enum):
    """Estado de archivo procesado: accepted | rejected."""

    accepted = "accepted"
    rejected = "rejected"


class NivelError(str, enum.Enum):
    """Nivel de error logueado: WARNING | ERROR | CRITICAL."""

    warning = "WARNING"
    error = "ERROR"
    critical = "CRITICAL"


class Resultado(str, enum.Enum):
    """Resultado de acción de remediación: success | failed."""

    success = "success"
    failed = "failed"


def enum_values(enum_class: type[enum.Enum]) -> list[str]:
    """Return member VALUES (not names) so storage matches the spec exactly.

    Required because SQLAlchemy defaults to member names, which diverge for
    ``NivelError`` (values ``WARNING/ERROR/CRITICAL`` vs names ``warning/...``).
    """

    return [member.value for member in enum_class]
