# Syncs & Remediation API Specification

## Purpose

Read endpoints for the Sincronizaciones screen (syncs with expandable files, server-side aggregates) and read/write endpoints for the Remediación screen plus remediation actions (RETRY_JOB, FORCE_SKIP_VALIDATION).

## Requirements

### Requirement 1: Sync list with files

GET /api/v1/syncs?include_files=true MUST return syncs ordered by iniciado_at DESC, each with: id, correlation_id, estado, fecha_ejecucion, iniciado_at, finalizado_at, usuario_origen, archivos_resumen ("N total · M rechazados" computed server-side), and, when include_files=true, an embedded `archivos` array (nombre_archivo, tipo_archivo, checksum, estado, registros_totales). Files MUST be loaded via selectinload — no N+1.

#### Scenario: Expandable rows data

- GIVEN 8 syncs with 3-5 files each
- WHEN GET /syncs?include_files=true
- THEN each sync carries its files and archivos_resumen matches "N total · M rechazados"
- AND the SQL query count stays constant regardless of file count

#### Scenario: Without files

- GIVEN the same data
- WHEN GET /syncs (include_files absent/false)
- THEN the archivos array is omitted but archivos_resumen remains

### Requirement 2: Remediation history

GET /api/v1/remediations MUST return remediations ordered by ejecutada_at DESC: id, sincronizacion_id, correlation_id (via join), accion_ejecutada, ejecutado_por, resultado, notas, ejecutada_at. The join MUST be N+1-free.

#### Scenario: History shape

- GIVEN seeded remediaciones
- WHEN GET /remediations
- THEN rows return newest-first with all screen columns

### Requirement 3: Record remediation

POST /api/v1/remediations MUST accept {sincronizacion_id, accion_ejecutada, ejecutado_por, resultado, notas?} and persist a row. Validation MUST reject an unknown accion_ejecutada (enum: RETRY_JOB, FORCE_SKIP_VALIDATION, MANUAL_REQUEUE, PURGE_DUPLICATE), a missing ejecutado_por (422), or an unknown sincronizacion_id (404). Success returns 201 with the created row.

#### Scenario: Record action

- GIVEN a valid sync id
- WHEN POST /remediations with {accion_ejecutada:"RETRY_JOB", ejecutado_por:"j.medina", resultado:"success", notas:"..."}
- THEN 201 returns and the row appears in GET /remediations

#### Scenario: Invalid action

- GIVEN accion_ejecutada="UNKNOWN_ACTION"
- WHEN POST /remediations
- THEN 422 with a structured error and no row persisted

### Requirement 4: Remediation actions

POST /api/v1/syncs/{id}/remediate with body {accion: "RETRY_JOB" | "FORCE_SKIP_VALIDATION"} MUST transition the sync: RETRY_JOB sets a failed/rejected sync to running and re-ingests its rejected files; FORCE_SKIP_VALIDATION marks rejected files accepted, skipping schema validation. Each invocation MUST persist an acciones_remediacion row (ejecutado_por defaults to svc.autoheal when absent). Unsupported action MUST return 422; unknown sync MUST return 404.

#### Scenario: Retry job

- GIVEN a failed sync
- WHEN POST /syncs/{id}/remediate {accion:"RETRY_JOB"}
- THEN the sync estado becomes running, a RETRY_JOB remediation row is persisted, and the response includes the updated sync

#### Scenario: Force skip validation

- GIVEN a sync with rejected files
- WHEN POST /syncs/{id}/remediate {accion:"FORCE_SKIP_VALIDATION"}
- THEN rejected files transition to accepted and a remediation row is recorded

## Acceptance Criteria

- include_files toggles embedded files; archivos_resumen computed server-side
- selectinload: constant query count on large datasets
- GET remediations newest-first; POST validates enum/required fields, 201 on success
- Remediation actions transition state and persist history; 404 unknown sync, 422 unsupported action
