# Data Model Specification

## Purpose

PostgreSQL 16 schema for Centinela: 4 tables (sincronizaciones, archivos_procesados, logs_errores, acciones_remediacion), native enums, UUID/serial keys, checksum idempotency guard, and CASCADE referential integrity. Backed by Alembic migrations; seed data mirrors plantilla.html.

## Requirements

### Requirement 1: Sincronizaciones table

The schema MUST define `sincronizaciones`: `id` UUID PK; `correlation_id` UUID NOT NULL with a UNIQUE index (required as FK target from logs_errores); `fecha_ejecucion` DATE NOT NULL; `estado` enum('pending','running','completed','failed','rejected') NOT NULL DEFAULT 'pending'; `iniciado_at` TIMESTAMPTZ NOT NULL; `finalizado_at` TIMESTAMPTZ NULL; `usuario_origen` VARCHAR(100) NOT NULL. The schema MUST index `estado`, `fecha_ejecucion`, and composite (`estado`,`fecha_ejecucion`) for KPI queries.

#### Scenario: FK target exists

- GIVEN migrations applied to an empty database
- WHEN the catalog is inspected
- THEN `sincronizaciones` exists with all columns and a unique index on `correlation_id`

### Requirement 2: Archivos procesados table

The schema MUST define `archivos_procesados`: `id` serial PK; `sincronizacion_id` FK → sincronizaciones.id ON DELETE CASCADE NOT NULL; `nombre_archivo` VARCHAR(255) NOT NULL; `tipo_archivo` enum('ventas','inventario','clientes') NOT NULL; `checksum` VARCHAR(64) NOT NULL UNIQUE (idempotency guard); `estado` enum('accepted','rejected') NOT NULL; `registros_totales` INTEGER NOT NULL DEFAULT 0; `datos_payload` JSONB NULL. MUST index `sincronizacion_id` and `estado` (rejected-files KPI).

#### Scenario: Unique checksum

- GIVEN a row with checksum X
- WHEN inserting a second row with the same checksum X
- THEN PostgreSQL rejects the insert on the unique constraint

### Requirement 3: Logs de errores table

The schema MUST define `logs_errores`: `id` serial PK (keyset pagination cursor); `correlation_id` FK → sincronizaciones.correlation_id ON DELETE CASCADE NOT NULL (indexed); `servicio_responsable` VARCHAR(100) NOT NULL; `nivel_error` enum('WARNING','ERROR','CRITICAL') NOT NULL; `codigo_error` VARCHAR(50) NOT NULL; `mensaje` TEXT NOT NULL; `stack_trace` TEXT NULL; `creado_at` TIMESTAMPTZ NOT NULL DEFAULT now(). MUST index (`creado_at` DESC) for newest-first listing.

#### Scenario: Cursor monotonicity

- GIVEN logs inserted in chronological order
- WHEN paging with keyset `id < cursor` ordered by id DESC
- THEN rows return newest-first with no gaps or duplicates across pages

### Requirement 4: Acciones de remediación table

The schema MUST define `acciones_remediacion`: `id` serial PK; `sincronizacion_id` FK → sincronizaciones.id ON DELETE CASCADE NOT NULL; `accion_ejecutada` VARCHAR(100) NOT NULL; `ejecutado_por` VARCHAR(100) NOT NULL; `resultado` enum('success','failed') NOT NULL; `notas` TEXT NULL; `ejecutada_at` TIMESTAMPTZ NOT NULL DEFAULT now() (drives the Fecha column). MUST index `sincronizacion_id` and `ejecutada_at`.

#### Scenario: Cascade delete

- GIVEN a sincronizacion with archivos, logs and remediaciones
- WHEN the sincronizacion row is deleted
- THEN all dependent rows are removed (CASCADE) with no orphans

### Requirement 5: Migrations and seed

Migrations MUST be Alembic (a single head revision creating tables, enums, indexes; `alembic upgrade head` idempotent). Seed MUST mirror plantilla.html: >=8 syncs across all 5 estados, files for the 3 tipo_archivo, the 8 error codes (ERR_CHECKSUM_MISMATCH..ERR_POOL_EXHAUSTED) across WARNING/ERROR/CRITICAL, and >=4 remediaciones. Seeds MUST be idempotent.

#### Scenario: Seed parity

- GIVEN a fresh migrated and seeded database
- WHEN querying counts
- THEN every estado, nivel_error, error code and remediation action from the mock dataset is present

## Acceptance Criteria

- `alembic upgrade head` succeeds on a clean DB; downgrade removes all objects
- Unique checksum constraint rejects duplicates at DB level
- CASCADE verified: deleting a sincronizacion removes its archivos/logs/remediaciones
- Seed re-runnable with stable counts
- Indexes present: sincronizaciones(correlation_id UNIQUE, estado, fecha_ejecucion), archivos_procesados(checksum UNIQUE, sincronizacion_id, estado), logs_errores(correlation_id, creado_at DESC)
