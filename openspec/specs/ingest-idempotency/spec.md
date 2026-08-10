# Ingest Idempotency Specification

## Purpose

Raw-bytes batch upload with SHA-256 idempotency: POST /api/v1/ingest accepts a raw stream plus metadata headers, computes the checksum incrementally, and guarantees replay-safe idempotent results keyed by correlation_id.

## Requirements

### Requirement 1: Raw stream upload with headers

The ingest endpoint MUST accept a raw request body (not multipart, not JSON envelope) with headers: `X-Correlation-Id` (UUID, optional), `X-File-Name` (string), `X-Tipo-Archivo` (one of ventas|inventario|clientes), `X-Checksum-SHA256` (64 hex chars, client expected checksum). Missing X-File-Name, invalid X-Tipo-Archivo, or malformed X-Checksum-SHA256 MUST yield HTTP 422 with a structured error body before reading the body.

#### Scenario: Valid upload

- GIVEN a client POSTing a CSV body with all four headers and a correct checksum
- WHEN the request reaches the endpoint
- THEN it is accepted, processed, and a sync + file record is persisted

#### Scenario: Invalid header

- GIVEN X-Tipo-Archivo=pdf (not in enum)
- WHEN the request is received
- THEN the API returns 422 before consuming the body

### Requirement 2: Incremental SHA-256

The server MUST compute SHA-256 incrementally over the streamed body in 8 KB chunks (read(8192)); the full body MUST NOT be buffered in memory. Hashing MUST NOT block the async event loop (CPU work offloaded to executor threads). The computed digest MUST be compared to X-Checksum-SHA256.

#### Scenario: Streamed checksum

- GIVEN a multi-MB body streamed in chunks
- WHEN the server computes the digest while reading
- THEN the final digest equals sha256 of the whole body and memory stays bounded

### Requirement 3: Checksum mismatch

When the computed SHA-256 differs from X-Checksum-SHA256, the endpoint MUST return HTTP 422 with error code ERR_CHECKSUM_MISMATCH and MUST persist a structured logs_errores row (nivel=ERROR, codigo=ERR_CHECKSUM_MISMATCH) tied to the correlation_id. No success sync/archivo records are created.

#### Scenario: Mismatch handling

- GIVEN a body whose computed checksum differs from the header
- WHEN processing completes
- THEN the response is 422 with ERR_CHECKSUM_MISMATCH
- AND a log row exists for that correlation_id with mismatch detail

### Requirement 4: Correlation id idempotency

The endpoint MUST treat X-Correlation-Id as the idempotency key: a repeat upload with an existing correlation_id MUST NOT re-ingest; it MUST return the ORIGINAL result with HTTP 200 and MUST append a WARNING log row ERR_DUPLICATE_BATCH. When X-Correlation-Id is absent, the server MUST generate a UUID fallback used for persistence, response, and logging.

#### Scenario: Duplicate replay

- GIVEN a previously ingested correlation_id
- WHEN the same correlation_id is POSTed again
- THEN the response is 200 with the original stored result
- AND a logs_errores row ERR_DUPLICATE_BATCH (WARNING) is persisted
- AND no duplicate archivo row is created

#### Scenario: Server fallback

- GIVEN a POST without X-Correlation-Id
- WHEN the request is processed
- THEN a server-generated UUID is assigned and echoed as correlation_id in response and log rows

### Requirement 5: Response contract

A first ingest MUST return HTTP 201 with JSON: correlation_id, sync id, estado, nombre_archivo, tipo_archivo, checksum, registros_totales. A duplicate replay MUST return HTTP 200 with the identical stored payload.

#### Scenario: Response shape

- GIVEN a successful first ingest
- WHEN the response is received
- THEN it contains correlation_id, sincronizacion id, estado, nombre_archivo, tipo_archivo, checksum, registros_totales

## Acceptance Criteria

- Same correlation_id twice: first 201, replay 200 with original payload + ERR_DUPLICATE_BATCH row; no duplicate rows
- Checksum mismatch: 422 + ERR_CHECKSUM_MISMATCH log row with correlation_id
- Fallback correlation_id generated when header absent
- Incremental hashing matches full-body sha256 with bounded memory
- Event loop stays responsive under concurrent uploads
