"""Shared dataset builders for API integration tests (Batch 2)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

from app.models import AccionRemediacion, ArchivoProcesado, LogError, Sincronizacion
from app.models.enums import ArchivoEstado, NivelError, Resultado, SyncEstado, TipoArchivo


def checksum(seed: str) -> str:
    """Deterministic 64-hex checksum (unique constraint + idempotency guard)."""
    return hashlib.sha256(seed.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sync_row(
    *,
    correlation_id: uuid.UUID | None = None,
    estado: SyncEstado = SyncEstado.completed,
    fecha: date | None = None,
    iniciado: datetime | None = None,
    finalizado: datetime | None = None,
    usuario: str = "svc.batch.ops",
) -> Sincronizacion:
    """A sync with deterministic-ish defaults; ids are always fresh."""
    return Sincronizacion(
        correlation_id=correlation_id or uuid.uuid4(),
        fecha_ejecucion=fecha or date.today(),
        estado=estado,
        iniciado_at=iniciado or utcnow() - timedelta(hours=1),
        finalizado_at=finalizado,
        usuario_origen=usuario,
    )


def archivo_row(
    sync: Sincronizacion,
    *,
    seed: str | None = None,
    tipo: TipoArchivo = TipoArchivo.ventas,
    estado: ArchivoEstado = ArchivoEstado.accepted,
    registros: int = 10,
) -> ArchivoProcesado:
    """An archivo attached to ``sync`` with a unique checksum."""
    return ArchivoProcesado(
        sincronizacion=sync,
        nombre_archivo=f"lote_{tipo.value}_{uuid.uuid4().hex[:8]}.csv",
        tipo_archivo=tipo,
        checksum=checksum(seed or uuid.uuid4().hex),
        estado=estado,
        registros_totales=registros,
    )


def log_row(
    sync: Sincronizacion,
    *,
    codigo: str = "ERR_DB_TIMEOUT",
    nivel: NivelError = NivelError.error,
    servicio: str = "DB_Connection_Pool",
    mensaje: str = "error de prueba",
    stack: str | None = None,
    creado: datetime | None = None,
) -> LogError:
    """A structured error log tied to ``sync.correlation_id``."""
    return LogError(
        correlation_id=sync.correlation_id,
        servicio_responsable=servicio,
        nivel_error=nivel,
        codigo_error=codigo,
        mensaje=mensaje,
        stack_trace=stack,
        creado_at=creado or utcnow(),
    )


def accion_row(
    sync: Sincronizacion,
    *,
    accion: str = "RETRY_JOB",
    ejecutado_por: str = "svc.autoheal",
    resultado: Resultado = Resultado.success,
    notas: str | None = None,
    ejecutada: datetime | None = None,
) -> AccionRemediacion:
    """A remediation history row for ``sync``."""
    return AccionRemediacion(
        sincronizacion_id=sync.id,
        accion_ejecutada=accion,
        ejecutado_por=ejecutado_por,
        resultado=resultado,
        notas=notas,
        ejecutada_at=ejecutada or utcnow(),
    )
