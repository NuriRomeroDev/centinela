"""Sincronizaciones ORM model (data-model spec Req 1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SyncEstado, enum_values

if TYPE_CHECKING:
    from app.models.accion_remediacion import AccionRemediacion
    from app.models.archivo import ArchivoProcesado
    from app.models.log_error import LogError


class Sincronizacion(Base):
    """Una ejecución de sincronización de lotes (idempotencia por correlation_id)."""

    __tablename__ = "sincronizaciones"
    __table_args__ = (
        Index("ix_sincronizaciones_estado", "estado"),
        Index("ix_sincronizaciones_fecha_ejecucion", "fecha_ejecucion"),
        Index("ix_sincronizaciones_estado_fecha_ejecucion", "estado", "fecha_ejecucion"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, index=True, nullable=False)
    fecha_ejecucion: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[SyncEstado] = mapped_column(
        Enum(SyncEstado, name="sync_estado", native_enum=True, values_callable=enum_values),
        nullable=False,
        default=SyncEstado.pending,
        server_default=text("'pending'"),
    )
    iniciado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalizado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usuario_origen: Mapped[str] = mapped_column(String(100), nullable=False)

    archivos: Mapped[list["ArchivoProcesado"]] = relationship(
        back_populates="sincronizacion", cascade="all, delete-orphan", passive_deletes=True
    )
    logs: Mapped[list["LogError"]] = relationship(
        back_populates="sincronizacion", cascade="all, delete-orphan", passive_deletes=True
    )
    acciones: Mapped[list["AccionRemediacion"]] = relationship(
        back_populates="sincronizacion", cascade="all, delete-orphan", passive_deletes=True
    )
