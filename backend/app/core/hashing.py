"""Incremental SHA-256 hashing — streaming, non-blocking (design §4.5).

CPU-bound work (``update``/``hexdigest``) is offloaded to executor threads so
the event loop stays free while hashing multi-MB bodies in 8 KB chunks.
"""

import asyncio
import hashlib

from app.core.errors import ChecksumMismatchError

DEFAULT_CHUNK_SIZE = 8192


class IncrementalSha256:
    """Streaming SHA-256 hasher with non-blocking async updates."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self.chunk_size = chunk_size
        self._hasher = hashlib.sha256()

    async def update(self, chunk: bytes) -> None:
        """Feed one chunk (offloaded to a thread)."""
        await asyncio.to_thread(self._hasher.update, chunk)

    async def hexdigest(self) -> str:
        """Final hex digest (offloaded to a thread)."""
        return await asyncio.to_thread(self._hasher.hexdigest)


def sha256_hex(data: bytes) -> str:
    """One-shot SHA-256 hex digest (sync helper)."""
    return hashlib.sha256(data).hexdigest()


def verify_checksum(expected: str, actual: str) -> None:
    """Raise :class:`ChecksumMismatchError` when the digests differ."""
    if expected != actual:
        raise ChecksumMismatchError(f"Checksum mismatch: expected {expected} got {actual}")
