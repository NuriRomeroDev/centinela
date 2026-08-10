"""Unit tests for the Centinela error taxonomy (T1.3).

RED phase: references ``app.core.errors`` which does not exist yet.
"""

import pytest

from app.core.errors import (
    ERROR_CODES,
    ERROR_HTTP_STATUS,
    AppError,
    ChecksumMismatchError,
    DbUnavailableError,
    DuplicateBatchError,
    JsonMalformedError,
    NetworkResetError,
    OrphanRecordError,
    PoolExhaustedError,
    ValidationRejectedError,
    http_status_for,
)

EXPECTED_CODES = {
    "ERR_CHECKSUM_MISMATCH",
    "ERR_DB_TIMEOUT",
    "ERR_SCHEMA_VALIDATION",
    "ERR_DUPLICATE_BATCH",
    "ERR_NETWORK_RESET",
    "ERR_ORPHAN_RECORD",
    "ERR_JSON_MALFORMED",
    "ERR_POOL_EXHAUSTED",
}

ERROR_CLASSES = (
    ChecksumMismatchError,
    DbUnavailableError,
    ValidationRejectedError,
    DuplicateBatchError,
    NetworkResetError,
    OrphanRecordError,
    JsonMalformedError,
    PoolExhaustedError,
)


def test_error_codes_registry_has_exactly_the_8_seed_codes():
    assert set(ERROR_CODES) == EXPECTED_CODES
    assert len(ERROR_CODES) == 8


@pytest.mark.parametrize("cls", ERROR_CLASSES)
def test_every_error_class_subclasses_app_error(cls):
    assert issubclass(cls, AppError)
    assert issubclass(AppError, Exception)


@pytest.mark.parametrize(
    ("cls", "expected_status"),
    [
        (ChecksumMismatchError, 422),
        (ValidationRejectedError, 422),
        (JsonMalformedError, 422),
        (NetworkResetError, 422),
        (OrphanRecordError, 422),
        (DuplicateBatchError, 200),
        (DbUnavailableError, 503),
        (PoolExhaustedError, 503),
    ],
)
def test_http_status_per_error_class(cls, expected_status):
    assert cls.status_code == expected_status


@pytest.mark.parametrize(
    ("codigo", "expected_status"),
    [
        ("ERR_CHECKSUM_MISMATCH", 422),
        ("ERR_SCHEMA_VALIDATION", 422),
        ("ERR_JSON_MALFORMED", 422),
        ("ERR_NETWORK_RESET", 422),
        ("ERR_ORPHAN_RECORD", 422),
        ("ERR_DUPLICATE_BATCH", 200),
        ("ERR_DB_TIMEOUT", 503),
        ("ERR_POOL_EXHAUSTED", 503),
    ],
)
def test_error_code_mapping(codigo, expected_status):
    assert http_status_for(codigo) == expected_status


def test_status_mapping_covers_every_registered_code():
    assert set(ERROR_HTTP_STATUS.keys()) == set(ERROR_CODES)


def test_error_body_shape_includes_codigo_mensaje_correlation_id():
    err = ChecksumMismatchError("checksum mismatch", correlation_id="abc-123")
    assert err.to_body() == {
        "error": {
            "codigo": "ERR_CHECKSUM_MISMATCH",
            "mensaje": "checksum mismatch",
            "correlation_id": "abc-123",
        }
    }


def test_default_message_used_when_mensaje_omitted():
    err = PoolExhaustedError()
    assert err.mensaje == PoolExhaustedError.mensaje_default
    assert str(err) == PoolExhaustedError.mensaje_default


def test_correlation_id_is_optional_and_nullable_in_body():
    err = JsonMalformedError("bad json")
    assert err.correlation_id is None
    assert err.to_body()["error"]["correlation_id"] is None
