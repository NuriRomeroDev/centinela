"""Incremental SHA-256 hashing — streaming, non-blocking (design §4.5).

CPU-bound work is offloaded in two ways:
- Streaming chunks: asyncio.to_thread (ThreadPoolExecutor) — keeps the event
  loop free while accumulating 8 KB increments across multiple await points.
- One-shot large payloads: loop.run_in_executor(ProcessPoolExecutor) — bypasses
  the GIL entirely for pure CPU work on already-buffered bytes.
"""

import asyncio
import hashlib
from concurrent.futures import ProcessPoolExecutor

from app.core.errors import ChecksumMismatchError

DEFAULT_CHUNK_SIZE = 8192

_process_pool = ProcessPoolExecutor(max_workers=2)


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
    """One-shot SHA-256 hex digest (sync — runs in executor)."""
    return hashlib.sha256(data).hexdigest()


async def sha256_hex_process(data: bytes) -> str:
    """One-shot SHA-256 via ProcessPoolExecutor — bypasses the GIL for large payloads."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_process_pool, sha256_hex, data)


def verify_checksum(expected: str, actual: str) -> None:
    """Raise :class:`ChecksumMismatchError` when the digests differ."""
    if expected != actual:
        raise ChecksumMismatchError(f"Checksum mismatch: expected {expected} got {actual}")
