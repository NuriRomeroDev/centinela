"""LogsErrores ORM model (data-model spec Req 3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import NivelError, enum_values


class LogError(Base):
    """Log estructurado de error, ligado a un correlation_id (FK a sincronizaciones)."""

    __tablename__ = "logs_errores"
    __table_args__ = (
        Index("ix_logs_errores_correlation_id", "correlation_id"),
        Index("ix_logs_errores_correlation_id_creado_at", "correlation_id", text("creado_at DESC")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sincronizaciones.correlation_id", ondelete="CASCADE"), nullable=False
    )
    servicio_responsable: Mapped[str] = mapped_column(String(100), nullable=False)
    nivel_error: Mapped[NivelError] = mapped_column(
        Enum(NivelError, name="nivel_error", native_enum=True, values_callable=enum_values),
        nullable=False,
    )
    codigo_error: Mapped[str] = mapped_column(String(50), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sincronizacion: Mapped["Sincronizacion"] = relationship(
        back_populates="logs",
        primaryjoin="Sincronizacion.correlation_id == LogError.correlation_id",
        foreign_keys="LogError.correlation_id",
    )
