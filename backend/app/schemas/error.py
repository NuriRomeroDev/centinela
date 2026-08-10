"""Error response schemas — ``{error: {codigo, mensaje, correlation_id}}`` (design §4.8)."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Structured error detail carried by every non-2xx response."""

    codigo: str
    mensaje: str
    correlation_id: str | None = None


class ErrorBody(BaseModel):
    """Envelope for all error responses."""

    error: ErrorDetail
