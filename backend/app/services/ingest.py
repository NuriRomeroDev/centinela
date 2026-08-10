"""Ingest processing: streamed body reading, incremental hashing, payload parsing (design §4.4/§4.5).

CPU-heavy work (per-chunk ``sha256.update``, ``hexdigest``, ``json.loads``,
record validation) is offloaded to executor threads via ``asyncio.to_thread`` so
the event loop never blocks while hashing or parsing multi-MB bodies. Memory
stays O(chunk) for hashing; the parsed payload is retained for JSONB storage.
"""

from __future__ import annotations

import asyncio
import json

from app.core.errors import JsonMalformedError, NetworkResetError, ValidationRejectedError
from app.core.hashing import IncrementalSha256

# Exceptions raised by the ASGI server when the peer resets/closes mid-stream.
RETRYABLE_STREAM_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
)

DEFAULT_CHUNK_SIZE = 8192


def _correlation_id(request) -> str | None:
    raw = request.headers.get("x-correlation-id")
    return raw or None


async def read_body_and_hash(request) -> tuple[str, bytes]:
    """Stream the raw body in 8 KB chunks, hashing incrementally in a thread.

    Returns ``(hex_digest, payload_bytes)``. A mid-stream reset raises
    :class:`NetworkResetError` (corruption-handling spec R2) — no partial
    digest is ever returned.
    """
    hasher = IncrementalSha256()
    chunks: list[bytes] = []
    try:
        async for chunk in request.stream():
            await hasher.update(chunk)
            chunks.append(chunk)
    except RETRYABLE_STREAM_EXCEPTIONS as exc:
        raise NetworkResetError(correlation_id=_correlation_id(request)) from exc
    digest = await hasher.hexdigest()
    return digest, b"".join(chunks)


def _parse_payload(payload: bytes, *, correlation_id: str | None) -> list[dict]:
    """Deserialize + validate the raw payload (runs in an executor thread).

    Contract: the payload MUST be a JSON array of objects; ``registros_totales``
    is its length. Parse failure → :class:`JsonMalformedError` (CRITICAL);
    wrong shape → :class:`ValidationRejectedError` (WARNING).
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise JsonMalformedError(correlation_id=correlation_id) from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValidationRejectedError(
            "El payload debe ser una lista de registros JSON.",
            correlation_id=correlation_id,
        )
    return data


async def parse_payload_async(payload: bytes, *, correlation_id: str | None) -> list[dict]:
    """Parse + validate the payload off the event loop (design §4.5)."""
    return await asyncio.to_thread(_parse_payload, payload, correlation_id=correlation_id)
