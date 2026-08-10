# Tasks: Plataforma Centinela — Fullstack Technical Test Delivery

Greenfield monorepo (FastAPI + React/PrimeReact + PostgreSQL + Docker + Jenkins). Strict TDD (`config.yaml apply.tdd: true`): every implementation task is preceded by its RED test task in the same batch. Batches are strictly ordered (1 → 2 → 3 → 4); each batch = one chained PR.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 6,500–8,500 total (PR1 ~1,200–1,600; PR2 ~1,600–2,200; PR3 ~3,200–4,200; PR4 ~500–700) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 backend+DB foundation → PR2 backend APIs+tests → PR3 frontend → PR4 devops/scripts/README |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain (pending user choice) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Base boundary |
|------|------|-----------|---------------|
| 1 | Backend+DB foundation: scaffold, config, error taxonomy, engine+retry, models, migration, seed, unit/schema tests | PR 1 | feature/tracker branch (`feat/plataforma-centinela`) |
| 2 | Backend APIs: ingest/idempotency/corruption, dashboard, logs, syncs/remediations + testcontainers integration tests | PR 2 | PR 1 branch |
| 3 | Frontend: scaffold+theme+shell+dashboard+logs virtualization+syncs/remediation + Vitest/RTL tests | PR 3 | PR 2 branch |
| 4 | DevOps: compose, Dockerfiles, scripts, Jenkinsfile, README | PR 4 | PR 3 branch |

## Batch 1: Foundation & Database (PR 1)

- [x] **T1.1** Repo scaffold — create `backend/`, `frontend/`, `scripts/`; root `.gitignore` (.env, node_modules, __pycache__, dist, .pytest_cache); `.env.example` with POSTGRES_*, DATABASE_URL, BACKEND_PORT, FRONTEND_PORT, CORS_ORIGINS, DB_RETRY_* placeholders (DO5). Deps: —. Spec: devops-docker R5.
- [x] **T1.2** Backend tooling — `backend/pyproject.toml` (FastAPI, SQLAlchemy 2, asyncpg, pydantic-settings, alembic; dev: pytest, pytest-asyncio, testcontainers, httpx, flake8, black, coverage) with lint + `pytest --cov --cov-fail-under=80` config (T4, DO4). Deps: T1.1. Spec: ci-jenkins R3/R4.
- [x] **T1.3** Core config + errors — `app/core/settings.py` (env: DATABASE_URL, CORS_ORIGINS, DB_RETRY_INITIAL_BACKOFF/MAX_ATTEMPTS/JITTER, pool params), `app/core/errors.py` AppError + 8 codes (ERR_CHECKSUM_MISMATCH, ERR_DB_TIMEOUT, ERR_SCHEMA_VALIDATION, ERR_DUPLICATE_BATCH, ERR_NETWORK_RESET, ERR_ORPHAN_RECORD, ERR_JSON_MALFORMED, ERR_POOL_EXHAUSTED) (BE6, BE8). Deps: T1.1. Spec: design §4.1/4.8, corruption-handling R3.
- [x] **T1.4** DB engine + retry — `app/db/engine.py` (create_async_engine, pool_size/overflow/timeout, pool_pre_ping), `app/db/retry.py` `retry_acquire()` (exponential backoff + jitter, bounded max_attempts, fail-fast PoolExhaustedError → 503), `app/db/session.py` get_session; startup probe + dispose (BE6). Deps: T1.3. Spec: corruption-handling R3.
- [x] **T1.5** ORM models — `app/models/enums.py` (sync estado, tipo_archivo, archivo estado, nivel_error, resultado) + 4 models with PKs, FKs ON DELETE CASCADE (archivos.sincronizacion_id→sincronizaciones.id, logs.correlation_id→sincronizaciones.correlation_id, acciones.sincronizacion_id→sincronizaciones.id), relationships (DB1). Deps: T1.3. Spec: data-model R1–R4.
- [x] **T1.6** RED: schema tests — testcontainers + `alembic upgrade head`: catalog has 4 tables/columns/enums/PKs; unique correlation_id + checksum; CASCADE delete removes dependents; JSONB nullable; defaults (registros_totales=0, creado_at, ejecutada_at) (DB1, DB2, DB3, T2). Deps: T1.5. Spec: data-model AC.
- [x] **T1.7** GREEN: Alembic migration — single head `0001_initial` creating enums, 4 tables, PKs, FKs CASCADE, UNIQUE (correlation_id, checksum), composite indexes (sincronizaciones (estado,fecha_ejecucion), archivos (sincronizacion_id, estado), logs (correlation_id, creado_at DESC), acciones (sincronizacion_id, ejecutada_at)), defaults, JSONB nullable; downgrade removes all (DB1, DB2, DB3). Deps: T1.6. Spec: data-model R1–R5.
- [x] **T1.8** Idempotent seed — mirrors plantilla.html: ≥8 syncs across 5 estados, files for 3 tipo_archivo, 8 error codes across WARNING/ERROR/CRITICAL with servicios (API_Gateway, Validation_Engine, Data_Worker, DB_Connection_Pool), ≥4 remediaciones; rerunnable with stable counts (DB1, BE8). Deps: T1.7. Spec: data-model R5.
- [x] **T1.9** Unit tests (no DB) — incremental SHA-256 == full-body sha256, checksum mismatch raises, retry backoff bounds + jitter with monkeypatched clock, error-code mapping (T1, BE1, BE4, BE6). Deps: T1.3, T1.4. Spec: ingest-idempotency R2, corruption-handling R3.

## Batch 2: Backend APIs (PR 2)

- [x] **T2.1** RED: ingest integration tests — testcontainers + httpx.AsyncClient: happy path 201 + response shape, replay 200 original + ERR_DUPLICATE_BATCH row + no dup archivo, fallback correlation_id, mismatch 422 + log row, malformed JSON 422 ERR_JSON_MALFORMED, schema fail 422 ERR_SCHEMA_VALIDATION, invalid header 422 before body read, concurrent corrupt+healthy isolation (BE1, BE2, BE3, BE4, T2). Deps: T1.9. Spec: ingest-idempotency R1–R5, corruption-handling R1/R4.
- [x] **T2.2** GREEN: ingest router + idempotency service — raw stream read(8192) chunks, `asyncio.to_thread(hasher.update)` + hexdigest, header validation, mismatch → 422 + log row (own txn), pre-check + IntegrityError catch (TOCTOU-safe) → 200 original, uuid4 fallback, single-txn commit (sync+archivo+JSONB) (BE1, BE2, BE3, BE4). Deps: T2.1. Spec: ingest-idempotency R1–R5.
- [x] **T2.3** Error handlers + structured logging — global AppError handler, RequestValidationError + IntegrityError → 422, ERR_NETWORK_RESET on truncated body; `logs_errores` row in fresh txn tied to correlation_id; body `{error:{codigo,mensaje,correlation_id}}` (BE3, BE8). Deps: T2.2. Spec: corruption-handling R1/R2/R4.
- [x] **T2.4** RED: dashboard integration tests — metrics aggregates + empty zeros, throughput 7d zero-fill + clamp 1–30, status-distribution shape, recent logs (no stack_trace, clamp 1–20), query-count assertion O(1) on 1,000 rows via SQLAlchemy event counter (BE5, BE7, T2). Deps: T2.3. Spec: dashboard-api R1–R5.
- [x] **T2.5** GREEN: dashboard API — metrics via func.count/sum/filter aggregates, throughput one GROUP BY + Python zero-fill, status-distribution sorted, logs/recent (BE5, BE7). Deps: T2.4. Spec: dashboard-api R1–R4.
- [x] **T2.6** RED: logs API integration tests — keyset walk (every row once, no gaps), search ILIKE + AND composition + filtered total, offset paging, detail with stack_trace + 404, empty shape items=[] (BE7, T1, T2). Deps: T2.5. Spec: logs-api R1–R4.
- [x] **T2.7** GREEN: logs API — keyset (`id < cursor`, id DESC) + offset (page/page_size ≤100), `search` + per-field filters (ILIKE, AND-composed), detail endpoint (BE7). Deps: T2.6. Spec: logs-api R1–R3.
- [x] **T2.8** RED: syncs/remediations integration tests — include_files toggle, archivos_resumen "N total · M rechazados", selectinload query-count constant, remediations list via join newest-first, POST validation (422 unknown accion, 404 unknown sync, 201), remediate transitions (RETRY_JOB → running; FORCE_SKIP_VALIDATION → files accepted) (BE5, BE7, T2). Deps: T2.7. Spec: syncs-api R1–R4.
- [x] **T2.9** GREEN: syncs + remediations API — selectinload(Sincronizacion.archivos), archivos_resumen server-side, GET/POST /remediations, POST /syncs/{id}/remediate with svc.autoheal default (BE5, BE7). Deps: T2.8. Spec: syncs-api R1–R4.
- [x] **T2.10** DB-down recovery test — monkeypatch pool acquire to raise / stop DB: request fails fast with 503 ERR_POOL_EXHAUSTED/ERR_DB_TIMEOUT (no hang), auto-recovers when DB returns; assert bounded wall time (BE6, T2). Deps: T2.3. Spec: corruption-handling R3.

## Batch 3: Frontend (PR 3)

- [x] **T3.1** Frontend scaffold — Vite + React 18 + TS strict, PrimeReact 10.x pinned, react-router v6, TanStack Query v5, Vitest + RTL, `styles/tokens.css` OKLCH palette A/B CSS variables + PrimeReact `--p-*` overrides (FE1, FE7). Deps: — (parallel to Batch 2). Spec: frontend-dashboard R1/R2, design D-2/D-5.
- [x] **T3.2** RED: useDebounce tests — native setTimeout/clearTimeout, exactly one request per burst of 5 keystrokes, "buscando…" while raw ≠ debounced, no lodash (FE3, T3). Deps: T3.1. Spec: frontend-logs-virtualization R2.
- [x] **T3.3** GREEN: hooks — `useDebounce(value, 300)` (no lodash), `useTheme` (data-theme + localStorage), `usePolling` (FE3). Deps: T3.2. Spec: frontend-logs-virtualization R2.
- [x] **T3.4** Shell + routing — Sidebar 248px (brand, 4 NavLinks, active = accent bg + 3px left bar, environment card), Header 64px (title/subtitle, ThemeToggle segmented Claro/Oscuro, avatar MR), routes / /logs /syncs /remediacion, active nav reflects route (FE8). Deps: T3.1. Spec: frontend-dashboard R1/R2.
- [x] **T3.5** RED: dashboard tests — KPI binding to metrics, polling refetchInterval 30s (fake timers), chart 7 bars accepted/rejected, status bars width=pct, recent-errors row click → /logs + modal, fetch failure shows retry (FE2, T3). Deps: T3.4. Spec: frontend-dashboard R3–R7.
- [x] **T3.6** GREEN: dashboard screen — api client + queries (useDashboardMetrics, useThroughput, useStatusDistribution, useRecentLogs with refetchInterval 30s + refetchOnWindowFocus), KpiCard (IBM Plex Mono 28px/700), ThroughputChart (PrimeReact Chart stacked, 140px), StatusDistribution (Tag + 6px bars), RecentErrors (FE1, FE2). Deps: T3.5. Spec: frontend-dashboard R3–R6.
- [x] **T3.7** RED: virtualization + modal tests — VirtualScroller bounded DOM at offset (only viewport+overscan rows, top=idx*56, spacer=rows*56), footer math (total/page_size pages, "Mostrando a–b de total"), focus trap (Escape closes + focus restore, Tab wrap, overlay mousedown closes), row click fetches detail (FE4, FE5, T3). Deps: T3.4. Spec: frontend-logs-virtualization R1/R3/R4/R5.
- [x] **T3.8** GREEN: Logs screen — PrimeReact VirtualScroller (itemSize 56, numToleratedItems 4, 480px viewport, lazy keyset pages via next_cursor), VirtualLogList/LogRow/LogsFooter (offset paging, scroll reset), StackTraceModal (Dialog, focus trap, stack_trace display), InputText debounced search, useLogs/useLogDetail (FE1, FE3, FE4, FE5). Deps: T3.7. Spec: frontend-logs-virtualization R1–R6.
- [x] **T3.9** Sincronizaciones + Remediación screens — DataTable + rowExpansion (embedded archivos grid: tipo/checksum/estado/registros; chevron 0.15s), archivos_resumen column, RemediationTable (Fecha/Sincronización/Acción/Ejecutado por/Resultado/Notas), useSyncs/useRemediations/useRemediate (mutation → Toast + invalidate dashboard/syncs/remediations) (FE1, FE6). Deps: T3.8. Spec: syncs-api + design §5.3.
- [x] **T3.10** Theme polish + badge contrast — statusVisual/levelVisual token maps with palette-A/B variants (light-on-dark chips in B, WCAG 2.2 AA), audit: zero hard-coded colors in components, PrimeReact var remap verified (FE7, FE8). Deps: T3.9. Spec: design D-4.

## Batch 4: DevOps (PR 4)

- [ ] **T4.1** docker-compose.yml — networks `frontend-net` + `db-net`; db (postgres:16-alpine, pg_isready healthcheck, named volume pgdata, env from .env) on db-net ONLY; frontend on frontend-net ONLY, no DATABASE_URL/DB env; backend bridges BOTH + depends_on db service_healthy + CORS_ORIGINS + retry envs; ports from .env (DO1, DO5). Deps: T3.10. Spec: devops-docker R1/R2/R5.
- [ ] **T4.2** Dockerfiles — backend `python:3.12-slim`, non-root appuser, uvicorn CMD; frontend multi-stage (node:18-alpine `npm ci`+build → nginx:alpine serving dist/ with SPA fallback) + nginx.conf (DO3). Deps: T4.1. Spec: devops-docker R2.
- [ ] **T4.3** Scripts — `scripts/up.sh` (build → up -d → wait db healthy → exec alembic upgrade head → optional SEED=1 → URLs; rerunnable, exit non-zero), `scripts/clean.sh` (`docker compose down -v`), `scripts/test.sh` (pytest --cov --cov-fail-under=80 + vitest run --coverage; exit non-zero on fail), all executable (DO2, T4). Deps: T4.2. Spec: devops-docker R3/R4.
- [ ] **T4.4** Jenkinsfile — declarative `pipeline { agent any; stages: checkout → lint (flake8 + black --check + eslint) → unit tests (coverage ≥80 gates) → docker build }`, fail-fast, no secrets (DO4, T4). Deps: T4.3. Spec: ci-jenkins R1–R6.
- [ ] **T4.5** README + CORS wiring — run instructions (up/clean/test, env copy), architecture overview, CORS_ORIGINS default to frontend origin; final .env.example sync (DO5). Deps: T4.4. Spec: devops-docker R5/R6.

## Eval-Coverage Matrix

| Anchor | Task(s) |
|--------|---------|
| DB1 (tables/columns/enums/PKs/FKs CASCADE) | T1.5, T1.6, T1.7 |
| DB2 (unique correlation_id/checksum, composite indexes) | T1.6, T1.7 |
| DB3 (JSONB nullable, defaults) | T1.6, T1.7 |
| BE1 (raw ingest, headers, incremental SHA-256 8KB, mismatch 422+log) | T1.9, T2.1, T2.2 |
| BE2 (idempotency 200 original + ERR_DUPLICATE_BATCH, TOCTOU, fallback) | T2.1, T2.2 |
| BE3 (corrupt payload → clean 422, no crash, log tied to correlation_id) | T2.1, T2.2, T2.3 |
| BE4 (async non-blocking, thread executors) | T1.9, T2.1, T2.2 |
| BE5 (N+1: selectinload + SQL aggregates + query-count tests) | T2.4, T2.5, T2.8, T2.9 |
| BE6 (retry backoff+jitter, bounded, fail-fast 503, auto-recover) | T1.3, T1.4, T2.10 |
| BE7 (API surface: dashboard, logs keyset+search, syncs+files, remediations, detail) | T2.4–T2.9 |
| BE8 (structured logging fields incl. servicios) | T1.3, T1.8, T2.3 |
| FE1 (PrimeReact: VirtualScroller, DataTable+rowExpansion, Dialog, Chart, InputText, Tag, Toast) | T3.1, T3.6, T3.8, T3.9 |
| FE2 (dashboard KPIs, 7-day chart, distribution, recent errors, 30s polling) | T3.5, T3.6 |
| FE3 (native 300ms debounce, no lodash) | T3.2, T3.3, T3.8 |
| FE4 (virtualized list: 56px/480px/overscan 4, keyset integration) | T3.7, T3.8 |
| FE5 (focus trap modal: Tab/Escape/restore, stack_trace detail) | T3.7, T3.8 |
| FE6 (syncs expandable + remediation table, plantilla parity) | T3.9 |
| FE7 (OKLCH A/B toggle, CSS vars, dark badge contrast) | T3.1, T3.10 |
| FE8 (fidelity: 248px sidebar, 64px header, screens) | T3.4, T3.10 |
| DO1 (≥2 isolated networks, backend bridges both) | T4.1 |
| DO2 (up.sh / clean.sh / test.sh) | T4.3 |
| DO3 (Dockerfiles: slim non-root, multi-stage nginx) | T4.2 |
| DO4 (Jenkinsfile declarative stages + lint + 80% gate) | T1.2, T4.4 |
| DO5 (.env.example, healthchecks, README) | T1.1, T4.1, T4.5 |
| T1 (backend unit: checksum, idempotency, backoff/jitter, keyset) | T1.9, T2.6 |
| T2 (backend integration: testcontainers, N+1, DB-down) | T1.6, T2.1, T2.4, T2.8, T2.10 |
| T3 (frontend: debounce, VirtualScroller, focus trap, polling) | T3.2, T3.5, T3.7 |
| T4 (coverage gates ≥80% both stacks) | T1.2, T4.3, T4.4 |
