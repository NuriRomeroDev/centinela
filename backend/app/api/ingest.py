"""POST /api/v1/ingest — raw-bytes idempotent ingest (design §4.4/§4.5, §4.7).

Header validation runs as a dependency BEFORE the body is streamed (invalid
headers → 422 without consuming the body). The body is hashed incrementally in
8 KB chunks with CPU work offloaded to executor threads; the digest is compared
to ``X-Checksum-SHA256``; the payload is parsed and persisted idempotently.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ChecksumMismatchError
from app.core.hashing import sha256_hex_process
from app.db.retry import retry_acquire
from app.models.enums import TipoArchivo
from app.schemas.ingest import IngestHeaders
from app.services.idempotency import ingest_batch
from app.services.ingest import parse_payload_async, read_body_and_hash

router = APIRouter(tags=["ingest"])


def _require_correlation_id(raw: str | None) -> uuid.UUID | None:
    if raw is None:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise RequestValidationError(
            [
                {
                    "loc": ("header", "x-correlation-id"),
                    "msg": "value is not a valid UUID",
                    "type": "value_error",
                }
            ]
        ) from exc


async def validate_ingest_headers(
    x_file_name: Annotated[str, Header(min_length=1, max_length=255)],
    x_tipo_archivo: Annotated[TipoArchivo, Header()],
    x_checksum_sha256: Annotated[str, Header(pattern=r"^[0-9a-fA-F]{64}$")],
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> IngestHeaders:
    """Dependency: validate all metadata headers BEFORE the body is read."""
    return IngestHeaders(
        correlation_id=_require_correlation_id(x_correlation_id),
        x_file_name=x_file_name,
        x_tipo_archivo=x_tipo_archivo,
        x_checksum_sha256=x_checksum_sha256,
    )


@router.post("/ingest")
async def ingest(
    request: Request,
    headers: IngestHeaders = Depends(validate_ingest_headers),
) -> JSONResponse:
    """Accept a raw stream, compute SHA-256 incrementally, persist idempotently."""
    cid = headers.correlation_id or uuid.uuid4()

    digest, payload = await read_body_and_hash(request)

    if digest != headers.x_checksum_sha256.lower():
        raise ChecksumMismatchError(correlation_id=str(cid))

    # Cross-verify the buffered payload using ProcessPoolExecutor (bypasses GIL
    # for CPU-bound work on already-buffered bytes — multiprocessing requirement).
    process_digest = await sha256_hex_process(payload)
    if process_digest != digest:
        raise ChecksumMismatchError(correlation_id=str(cid))

    records = await parse_payload_async(payload, correlation_id=str(cid))

    engine = request.app.state.engine
    factory = request.app.state.session_factory
    async with retry_acquire(engine) as conn:
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            status, body = await ingest_batch(
                session,
                factory,
                correlation_id=cid,
                file_name=headers.x_file_name,
                tipo_archivo=headers.x_tipo_archivo,
                checksum=digest,
                payload=records,
            )

    return JSONResponse(status_code=status, content=body)
