"""Ingest service unit tests (no DB) — T2.1/T2.3 network-reset path.

The body reader must abort cleanly with ``ERR_NETWORK_RESET`` when the peer
resets mid-stream (corruption-handling spec R2): no partial digest, no crash.
"""

import pytest

from app.core.errors import NetworkResetError


class _FakeRequest:
    """Duck-typed Request: headers + stream() raising mid-stream."""

    def __init__(self, *, chunks: list[bytes], fail_after: int = 1):
        self._chunks = chunks
        self._fail_after = fail_after
        self.headers = {"x-correlation-id": "123e4567-e89b-12d3-a456-426614174000"}

    async def stream(self):
        for i, chunk in enumerate(self._chunks):
            if i >= self._fail_after:
                raise ConnectionResetError("connection reset by peer")
            yield chunk


async def test_read_body_and_hash_raises_network_reset_on_truncated_stream():
    from app.services.ingest import read_body_and_hash

    request = _FakeRequest(chunks=[b"[1,2,", b"3,4,5]", b"rest-of-body"], fail_after=2)

    with pytest.raises(NetworkResetError) as exc_info:
        await read_body_and_hash(request)

    assert exc_info.value.codigo == "ERR_NETWORK_RESET"
    assert exc_info.value.status_code == 422
    assert exc_info.value.correlation_id == "123e4567-e89b-12d3-a456-426614174000"


async def test_read_body_and_hash_returns_digest_and_bytes_on_clean_stream():
    from app.core.hashing import sha256_hex
    from app.services.ingest import read_body_and_hash

    body = b'[{"id": 1}, {"id": 2}]'
    request = _FakeRequest(chunks=[body[:5], body[5:]], fail_after=99)

    digest, payload = await read_body_and_hash(request)

    assert digest == sha256_hex(body)
    assert payload == body
