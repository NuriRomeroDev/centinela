"""ArchivosProcesados ORM model (data-model spec Req 2)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ArchivoEstado, TipoArchivo, enum_values

if TYPE_CHECKING:
    from app.models.sincronizacion import Sincronizacion


class ArchivoProcesado(Base):
    """Archivo procesado dentro de una sincronización (checksum = guard de idempotencia)."""

    __tablename__ = "archivos_procesados"
    __table_args__ = (
        Index("ix_archivos_procesados_sincronizacion_id", "sincronizacion_id"),
        Index("ix_archivos_procesados_estado", "estado"),
        Index("ix_archivos_procesados_sincronizacion_id_estado", "sincronizacion_id", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sincronizacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sincronizaciones.id", ondelete="CASCADE"), nullable=False
    )
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_archivo: Mapped[TipoArchivo] = mapped_column(
        Enum(TipoArchivo, name="tipo_archivo", native_enum=True, values_callable=enum_values),
        nullable=False,
    )
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    estado: Mapped[ArchivoEstado] = mapped_column(
        Enum(ArchivoEstado, name="archivo_estado", native_enum=True, values_callable=enum_values),
        nullable=False,
    )
    registros_totales: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    datos_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    sincronizacion: Mapped["Sincronizacion"] = relationship(back_populates="archivos")
