# Dashboard API Specification

## Purpose

Aggregate read endpoints powering the Dashboard screen: 4 KPI metrics, 7-day throughput, status distribution, and recent error logs, with N+1-free queries and stable response shapes.

## Requirements

### Requirement 1: KPI metrics endpoint

GET /api/v1/dashboard/metrics MUST return: sincronizaciones_activas (estado=running), completadas_hoy (estado=completed AND fecha_ejecucion=today, calendar day), archivos_rechazados (count of archivos estado=rejected), tasa_errores_criticos (CRITICAL logs / total logs percent, 1 decimal). MUST use SQL aggregates — full tables MUST NOT be loaded into memory.

#### Scenario: KPI computation

- GIVEN seeded data matching the mock
- WHEN GET /dashboard/metrics
- THEN the response matches the mock KPIs (running count, completed-today count, rejected files sum, error rate %)

#### Scenario: Empty dataset

- GIVEN no syncs or logs
- WHEN GET /dashboard/metrics
- THEN zeros are returned (0, 0, 0, "0.0") without error

### Requirement 2: Throughput endpoint

GET /api/v1/throughput?days=7 MUST return one entry per day for the last N days (default 7): date/label, aceptados (files estado=accepted), rechazados (files estado=rejected). Days with no data MUST appear with zero counts. days MUST be clamped to 1-30.

#### Scenario: Full week

- GIVEN sync files across the last 7 days
- WHEN GET /throughput?days=7
- THEN 7 entries return oldest-to-newest with accepted/rejected counts per day

#### Scenario: Sparse days

- GIVEN files only on 2 of the last 7 days
- WHEN GET /throughput
- THEN the other 5 days return zero counts

### Requirement 3: Status distribution endpoint

GET /api/v1/status-distribution MUST return per-estado {estado, count, pct} over the 5 estados sorted by count desc, pct to 1 decimal. Counts MUST sum to total syncs and pct to ~100.

#### Scenario: Distribution shape

- GIVEN seeded syncs across estados
- WHEN GET /status-distribution
- THEN each estado has {estado, count, pct} and counts sum to the total number of syncs

### Requirement 4: Recent logs endpoint

GET /api/v1/logs/recent?limit=5 MUST return the newest logs (order creado_at DESC, id DESC) with id, correlation_id, nivel_error, codigo_error, mensaje, servicio_responsable, creado_at. MUST NOT include stack_trace. limit MUST be clamped 1-20 (default 5).

#### Scenario: Latest five

- GIVEN 38 seeded logs
- WHEN GET /logs/recent?limit=5
- THEN the 5 most recent logs return newest-first without stack_trace

### Requirement 5: N+1 free reads

Dashboard endpoints MUST NOT exhibit N+1: aggregates use SQL aggregate queries; any collection loads use SQLAlchemy selectinload (or a single query). Tests MUST assert constant query count independent of row count.

#### Scenario: Constant query count

- GIVEN a dataset of 1,000 syncs/logs
- WHEN each dashboard endpoint is exercised
- THEN the SQL query count is constant (O(1)) regardless of dataset size

## Acceptance Criteria

- All 4 endpoints return documented JSON shapes with correct aggregates
- Zero-count behavior on empty data; clamp behavior on days/limit params
- No N+1: query-count test on a large dataset
- Response within time bounds on the seeded dataset
