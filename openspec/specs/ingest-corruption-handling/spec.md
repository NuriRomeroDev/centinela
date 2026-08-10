# Ingest Corruption Handling Specification

## Purpose

Graceful degradation when payloads are corrupted, truncated, or infrastructure (DB) fails: clean 4xx responses, structured log rows tied to correlation_id, and zero impact on service availability.

## Requirements

### Requirement 1: Malformed payload

A body that fails parsing or schema validation MUST return HTTP 422 and persist a structured log row tied to the correlation_id (header or fallback): nivel=CRITICAL codigo=ERR_JSON_MALFORMED on parse failure, nivel=WARNING codigo=ERR_SCHEMA_VALIDATION on schema failure. The process MUST NOT crash and other endpoints MUST remain available.

#### Scenario: JSON parse failure

- GIVEN a body with invalid JSON in the payload section
- WHEN processing attempts to parse it
- THEN 422 is returned with ERR_JSON_MALFORMED
- AND a CRITICAL log row exists for the correlation_id
- AND a subsequent dashboard request succeeds

### Requirement 2: Truncated / reset body

If the peer resets the connection or the body ends prematurely (ERR_NETWORK_RESET), the server MUST abort cleanly: no partial success records committed, HTTP 422/400 returned when the response is still possible, and an ERROR log row ERR_NETWORK_RESET tied to the correlation_id persisted.

#### Scenario: Connection reset mid-stream

- GIVEN a stream interrupted by the peer before completion
- WHEN the server detects the reset
- THEN no sync/archivo rows are committed for the partial body
- AND an ERR_NETWORK_RESET log row is persisted for the correlation_id

### Requirement 3: Database outage resilience

On PostgreSQL outage, ingest MUST NOT hang HTTP requests: connection acquisition applies bounded retry with exponential backoff + jitter and fails fast after max attempts with structured errors ERR_DB_TIMEOUT or ERR_POOL_EXHAUSTED (CRITICAL). The retry policy MUST be configurable via environment (initial backoff, max attempts, jitter).

#### Scenario: Pool exhausted

- GIVEN the connection pool is saturated
- WHEN a new ingest acquires a connection
- THEN the request fails within a bounded wait with ERR_POOL_EXHAUSTED
- AND a CRITICAL log row is persisted (or surfaced) without hanging

#### Scenario: Bounded retry

- GIVEN DB unavailable at the first attempt
- WHEN the ingest retries
- THEN retries use exponential backoff + jitter and stop at max attempts
- AND the request returns an error rather than waiting indefinitely

### Requirement 4: Availability preservation

Error handling MUST be scoped per-request: one corrupt payload MUST NOT affect concurrent ingests or read endpoints. All error paths MUST return a structured JSON error body {error: {codigo, mensaje, correlation_id}} with the appropriate status code.

#### Scenario: Concurrent isolation

- GIVEN one corrupt ingest and one healthy ingest in flight
- WHEN both complete
- THEN the healthy one succeeds normally while the corrupt one returns 422
- AND both produce correct log rows

## Acceptance Criteria

- Corrupt/truncated/mismatched payloads: clean 4xx + structured error + log row with correlation_id; no crash
- No partial commits on failure (transactional)
- DB outage: bounded retry (backoff + jitter, env-configurable), fail-fast with ERR_DB_TIMEOUT/ERR_POOL_EXHAUSTED
- Availability: concurrent healthy requests unaffected; error body shape {error:{codigo,mensaje,correlation_id}}
