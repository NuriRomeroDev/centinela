"""Ingest request/response schemas (ingest-idempotency spec R1/R5)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import SyncEstado, TipoArchivo


class IngestHeaders(BaseModel):
    """Validated ingest metadata headers (raw body is streamed separately)."""

    correlation_id: uuid.UUID | None = None
    x_file_name: str = Field(min_length=1, max_length=255)
    x_tipo_archivo: TipoArchivo
    x_checksum_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class IngestResponse(BaseModel):
    """201 first-ingest / 200 replay payload (ingest-idempotency spec R5)."""

    correlation_id: uuid.UUID
    sync_id: uuid.UUID
    estado: SyncEstado
    nombre_archivo: str
    tipo_archivo: TipoArchivo
    checksum: str
    registros_totales: int
