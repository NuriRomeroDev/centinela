"""Unit tests for incremental SHA-256 hashing (T1.9). No DB.

RED phase: references ``app.core.hashing`` which does not exist yet.
"""

import hashlib

import pytest

from app.core.errors import ChecksumMismatchError
from app.core.hashing import IncrementalSha256, sha256_hex, verify_checksum


async def test_incremental_equals_one_shot_full_body():
    body = b"A" * 100_000  # spans multiple 8192-byte chunks
    hasher = IncrementalSha256()
    for start in range(0, len(body), 8192):
        await hasher.update(body[start : start + 8192])
    assert await hasher.hexdigest() == hashlib.sha256(body).hexdigest()


async def test_incremental_multiple_arbitrary_chunks():
    chunks = [b"foo", b"bar", b"baz-qux" * 1000]
    body = b"".join(chunks)
    hasher = IncrementalSha256()
    for chunk in chunks:
        await hasher.update(chunk)
    assert await hasher.hexdigest() == hashlib.sha256(body).hexdigest()


async def test_incremental_empty_body():
    hasher = IncrementalSha256()
    assert await hasher.hexdigest() == hashlib.sha256(b"").hexdigest()


def test_sha256_hex_returns_64_hex_chars():
    digest = sha256_hex(b"payload")
    assert len(digest) == 64
    assert digest == hashlib.sha256(b"payload").hexdigest()


def test_verify_checksum_passes_when_digests_match():
    digest = sha256_hex(b"data")
    verify_checksum(expected=digest, actual=digest)  # must not raise


def test_verify_checksum_raises_checksum_mismatch_error():
    with pytest.raises(ChecksumMismatchError) as exc_info:
        verify_checksum(expected="a" * 64, actual="b" * 64)
    assert exc_info.value.codigo == "ERR_CHECKSUM_MISMATCH"
    assert exc_info.value.status_code == 422
