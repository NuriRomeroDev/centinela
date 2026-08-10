"""AccionesRemediacion ORM model (data-model spec Req 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Resultado, enum_values


class AccionRemediacion(Base):
    """Acción de remediación ejecutada sobre una sincronización."""

    __tablename__ = "acciones_remediacion"
    __table_args__ = (
        Index("ix_acciones_remediacion_sincronizacion_id", "sincronizacion_id"),
        Index("ix_acciones_remediacion_ejecutada_at", "ejecutada_at"),
        Index("ix_acciones_remediacion_sincronizacion_id_ejecutada_at", "sincronizacion_id", "ejecutada_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sincronizacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sincronizaciones.id", ondelete="CASCADE"), nullable=False
    )
    accion_ejecutada: Mapped[str] = mapped_column(String(100), nullable=False)
    ejecutado_por: Mapped[str] = mapped_column(String(100), nullable=False)
    resultado: Mapped[Resultado] = mapped_column(
        Enum(Resultado, name="resultado", native_enum=True, values_callable=enum_values),
        nullable=False,
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    ejecutada_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sincronizacion: Mapped["Sincronizacion"] = relationship(back_populates="acciones")
