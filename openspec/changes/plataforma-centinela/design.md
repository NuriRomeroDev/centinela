# Design: Plataforma Centinela — Fullstack Technical Test Delivery

> Phase: sdd-design · Change: `plataforma-centinela` · Stack: FastAPI (async) + React 18 + PrimeReact + PostgreSQL 16 + Docker + Jenkins.
> Sources: `proposal.md` (locked decisions), the 10 specs in `openspec/specs/*`, `openspec/explorations/plataforma-centinela.md` (UI inventory + OKLCH tokens), `plantilla.html` (reference mock).

## 1. Context

Greenfield monorepo delivering the fixed-scope technical test "Centinela": a banking reconciliation and idempotency control platform. The backend ingests raw batch payloads with SHA-256 idempotency (replay-safe by `correlation_id`), the frontend replicates `plantilla.html` (dashboard KPIs, throughput chart, status distribution, recent errors, virtualized logs with 300 ms debounced search, expandable sync rows, remediation history, stack-trace modal with focus trap), and delivery is dockerized with network isolation plus a declarative Jenkins pipeline. All behavior is pinned by the 10 specs; this design decides HOW each is built.

## 2. Goals / Non-Goals

**Goals**

- Idempotent, corruption-tolerant ingest that never hangs on DB outage (bounded retry + fail-fast).
- N+1-free read APIs (SQL aggregates + `selectinload`); keyset + offset pagination for logs.
- Pixel-faithful frontend: 248 px sidebar / 64 px header, 56 px rows / 480 px viewport / overscan 4, native 300 ms debounce, OKLCH palette A/B toggle, accessible focus trap.
- Docker compose with network isolation (frontend cannot reach DB by construction); lifecycle + test scripts; Jenkinsfile gating at 80 % coverage.
- Strict TDD: tests before implementation per task (`config.yaml` `apply.tdd: true`).

**Non-Goals** (from proposal)

- Real auth, production deploy/CI publish, E2E browser tests.
- Dark-mode badge variants were listed out of scope by the proposal — **superseded** by design decision D-4 (a11y contrast wins; cost is minimal, two token rows).

## 3. Architecture Overview

```
┌──────────────┐  HTTPS/CORS   ┌──────────────────────────────┐
│  Browser SPA │──────────────▶│  Backend (FastAPI async)     │
│  React+PR    │   /api/v1/*   │  uvicorn · SQLAlchemy 2.0    │
│  nginx       │               │  services: idempotency,      │
└──────────────┘               │  ingest, metrics             │
    net: frontend-net          │  executors (asyncio.to_thread)│
                               └──────────────┬───────────────┘
                                              │ asyncpg (bounded retry pool)
    frontend-net ──── backend bridges both networks ──── db-net
                                              │
                                    ┌─────────▼─────────┐
                                    │ PostgreSQL 16     │
                                    │ 4 tables, enums,  │
                                    │ unique checksum   │
                                    └───────────────────┘
```

Ingest sequence (complex flow — see `rules.design`):

```
Client ── POST /api/v1/ingest (raw body + 4 headers)
  1. Header validation (X-File-Name, X-Tipo-Archivo enum, X-Checksum-SHA256 hex) → 422 before reading body
  2. correlation_id = X-Correlation-Id | uuid4() fallback
  3. Stream body read(8192) → await asyncio.to_thread(hasher.update, chunk)   [loop stays free]
  4. digest == X-Checksum-SHA256?  NO → 422 ERR_CHECKSUM_MISMATCH + log row (own txn)
  5. Pre-check: correlation_id already ingested?  YES → 200 original + ERR_DUPLICATE_BATCH WARNING
  6. Insert sincronizacion + archivo (payload parsed in thread) — one transaction
       IntegrityError on unique checksum → treat as duplicate → 200 original (TOCTOU-safe)
  7. 201 {correlation_id, sync_id, estado, nombre_archivo, tipo_archivo, checksum, registros_totales}
```

DB outage: connection acquisition is wrapped in a bounded retry (exponential backoff + jitter, env-configurable). Exhausted attempts fail fast — the request returns 503 `ERR_DB_TIMEOUT` / `ERR_POOL_EXHAUSTED` instead of hanging. Retries happen at acquisition only; side-effecting writes never blind-retry at the HTTP layer (the idempotency guard is the only write-retry authority).

## 4. Backend Design

### 4.1 Layout

```
backend/
├── app/
│   ├── main.py          # create_app(): lifespan, CORS, routers, exception handlers
│   ├── api/             # routers: ingest.py, dashboard.py, logs.py, syncs.py, remediations.py
│   ├── core/            # settings.py (pydantic-settings), logging.py, errors.py (AppError taxonomy, 8 codes)
│   ├── db/              # engine.py (pool + retry_acquire), session.py (get_session), base.py
│   ├── models/          # enums.py, sincronizacion.py, archivo.py, log_error.py, accion_remediacion.py
│   ├── schemas/         # pydantic v2 request/response: ingest, dashboard, logs, syncs, remediations, error
│   └── services/        # idempotency.py, ingest.py, metrics.py, retry.py
├── migrations/          # alembic: env.py, versions/0001_initial.py (single head: tables+enums+indexes)
├── tests/               # unit/, integration/, conftest.py (testcontainers + AsyncClient + query counter)
├── pyproject.toml       # deps, black/flake8/pytest/coverage config
├── Dockerfile           # python slim, non-root
└── .dockerignore
```

### 4.2 Engine, pool, retry (D-1)

`create_async_engine(DATABASE_URL, poolclass=AsyncAdaptedQueuePool, pool_size=20, max_overflow=10, pool_timeout=5, pool_pre_ping=True)` — all tunable via env. `pool_pre_ping` evicts stale connections so a DB restart recovers without waiting on a dead connection.

**Retry strategy — engine-level, not HTTP middleware.** `db/retry.py` exposes `retry_acquire()`: a context manager wrapping `engine.connect()` that retries on `OSError` / `TimeoutError` / `ConnectionRefusedError` with backoff `initial * 2^n ± jitter`, `max_attempts` (default 3), failing fast with `PoolExhaustedError` (→ 503 `ERR_POOL_EXHAUSTED`). Rationale: middleware-level retry cannot distinguish safe reads from side-effecting writes — retrying a POST with an ambiguous transaction outcome risks double-commit; retrying at acquisition keeps semantics local and matches the mock's `ERR_DB_TIMEOUT` trace (`pool.acquire(timeout=5.0)`).

**Lifespan integration:** on startup `retry_acquire()` performs one bounded connectivity probe so boot races with the compose DB healthcheck surface early (never hang); on shutdown `await engine.dispose()`. Requests never wait past `pool_timeout` + bounded retries.

### 4.3 Dependency injection

`get_session` async dependency yields an `AsyncSession` from a single `async_sessionmaker(expire_on_commit=False)`, closed by FastAPI after the request. Routers depend on services; services take the session. Per-request scoping preserves corrupt-payload isolation (spec: concurrent isolation scenario).

### 4.4 Idempotency flow (services/idempotency.py + ingest.py)

1. Header validation in the router → 422 before consuming the body.
2. `correlation_id` = header UUID or `uuid4()` fallback (propagated to response and log rows).
3. Streaming: iterate `request.stream()` in 8 KB chunks; hash via `asyncio.to_thread(hasher.update, chunk)`; final `hexdigest()` also in a thread. Memory stays O(chunk).
4. Mismatch → 422 + `ERR_CHECKSUM_MISMATCH` (ERROR) log row.
5. Duplicate detection is **two-layered**: (a) pre-check `SELECT` on `sincronizaciones.correlation_id`; (b) catch `IntegrityError` on the unique `checksum` constraint — TOCTOU-safe under concurrency. Both paths: load the original row, return 200 with the identical stored payload, persist `ERR_DUPLICATE_BATCH` (WARNING).
6. Commit is a single transaction (sync + archivo + parsed JSONB payload). On failure the transaction rolls back — no partial records; the error log row is inserted in a **fresh session/transaction** so it survives the rollback and stays tied to `correlation_id`.

### 4.5 CPU-bound work offloading

`asyncio.to_thread` for: per-chunk `sha256.update`, final `hexdigest`, JSONB payload `json.loads`, record schema validation (pydantic v2 is sync). Async reads (`request.stream()`, DB I/O) stay on the loop. Satisfies "hashing must not block the event loop" with bounded memory.

### 4.6 N+1 mitigation

- `GET /syncs?include_files=true` → `selectinload(Sincronizacion.archivos)`; `archivos_resumen` ("N total · M rechazados") computed server-side from the loaded collection.
- `GET /remediations` → `selectinload` / single join to fetch `correlation_id` via the sync.
- KPIs → 4 aggregate statements (`func.count`, `func.sum`, `func.count().filter()`) — never full-table loads. Throughput → one `GROUP BY fecha` query + zero-fill in Python.
- Enforced by a query-count test (SQLAlchemy `event` statement counter) asserting O(1) queries on a 1,000-row dataset.

### 4.7 API surface (Pydantic v2 request/response models)

| Endpoint | Method | Notes |
|---|---|---|
| `/api/v1/ingest` | POST | Raw body; headers `X-Correlation-Id?`, `X-File-Name`, `X-Tipo-Archivo`, `X-Checksum-SHA256`. 201 / 200 replay / 422 / 503 |
| `/api/v1/dashboard/metrics` | GET | `{activas, completadas_hoy, archivos_rechazados, tasa_errores_criticos}` — zeros on empty |
| `/api/v1/throughput?days=7` | GET | days clamped 1–30; zero-fill sparse days; oldest→newest |
| `/api/v1/status-distribution` | GET | `[{estado, count, pct}]`, pct 1 dp, sorted count desc |
| `/api/v1/logs/recent?limit=5` | GET | limit clamped 1–20; **no** `stack_trace` |
| `/api/v1/logs` | GET | keyset `cursor` AND offset `page/page_size` (page_size ≤ 100, default 25); `search` + per-field `mensaje`/`codigo_error`/`servicio_responsable` (ILIKE, AND-composed); returns `{items, total, next_cursor, page_size}` |
| `/api/v1/logs/{id}` | GET | full row incl. `stack_trace`; 404 unknown |
| `/api/v1/syncs?include_files=true` | GET | ordered `iniciado_at DESC`; files embedded only when flag set; `archivos_resumen` always |
| `/api/v1/remediations` | GET | ordered `ejecutada_at DESC`, incl. `correlation_id` via join |
| `/api/v1/remediations` | POST | `{sincronizacion_id, accion_ejecutada, ejecutado_por, resultado, notas?}` → 201 / 422 / 404 |
| `/api/v1/syncs/{id}/remediate` | POST | `{accion}` in {RETRY_JOB, FORCE_SKIP_VALIDATION}; transitions estado + persists history row (`ejecutado_por` defaults `svc.autoheal`); 200 / 422 / 404 |

### 4.8 Error handling

`core/errors.py` defines `AppError(status, codigo)` with the 8 seed codes (`ERR_CHECKSUM_MISMATCH` … `ERR_POOL_EXHAUSTED`). One global `AppError` handler + handlers for `RequestValidationError` and `IntegrityError` (→ 422). Every handler: persists a `logs_errores` row (own transaction) tied to `correlation_id` when available, then returns `{error: {codigo, mensaje, correlation_id}}`. Status map: **422** payload/validation/integrity (incl. truncated-body `ERR_NETWORK_RESET`), **404** unknown resources, **503** DB outage. Availability preserved: handlers are per-request; healthy concurrent requests unaffected.

## 5. Frontend Design

### 5.1 Stack & versions

Vite + React 18 + TypeScript `strict: true`; react-router-dom v6; TanStack Query v5; PrimeReact **stable 10.x pinned** (D-5: no v11 alpha); Vitest + RTL. Native `setTimeout`/`clearTimeout` debounce — no lodash (spec contract).

### 5.2 Theme strategy: OKLCH tokens → CSS variables (D-2)

`styles/tokens.css` defines `:root[data-theme='a']` and `[data-theme='b']` custom properties with the exact OKLCH values from exploration §2.7 (bg, sidebar*, nav*, accent, headerBg, cardBg/Border, rowBorder, textPrimary/Secondary, trackBg, tagBg, subRowBg, toggleTrack, avatar*, traceBg/Text, focusRing). Theme toggle sets `data-theme` on `<html>` (palette A = light, B = dark); optional `localStorage` persistence. **No hard-coded colors in components** — all surfaces consume tokens. PrimeReact components read the tokens through targeted CSS-variable overrides (mapping PrimeReact component vars — `--p-*` surface/color tokens — onto our OKLCH values; apply verifies which component vars need remapping per pinned version).

### 5.3 Mock → PrimeReact component mapping

| Mock surface | PrimeReact component | Key props / notes |
|---|---|---|
| Logs virtualized list | `VirtualScroller` | `itemSize=56`, `numToleratedItems=4` (overscan), viewport style `height:480px`, lazy mode fetching keyset pages; row `top = idx*56` |
| Sincronizaciones table | `DataTable` + `rowExpansion` | expandable rows with embedded archivos grid; chevron rotate 0.15 s |
| Stack-trace modal | `Dialog` | built-in focus trap (verify per version), `closable`, overlay mousedown → `onHide`; fallback `useFocusTrap` hook (D-3) |
| Throughput chart | `Chart` (chart.js) | stacked bars, 140 px area, legend 8×8 swatches |
| Search input | `InputText` | 300 ms debounced, focus ring token |
| Status / level / estado badges | `Tag` | token-driven `statusVisual`/`levelVisual` maps incl. palette-B variants (D-4) |
| KPI cards, lists | Plain styled components | typography: IBM Plex Mono 28px/700 values, code 11.5px mono |

### 5.4 Routing & data

- Routes: `/` → Dashboard, `/logs`, `/syncs`, `/remediacion`. Sidebar `NavLink`s with active state = accent bg + 3 px left bar; header title/subtitle per route (mock titles).
- TanStack Query hooks in `api/queries/`: `useDashboardMetrics`, `useThroughput`, `useStatusDistribution`, `useRecentLogs`, `useLogs` (keyset/offset + filters), `useLogDetail`, `useSyncs`, `useRemediations`, `useRemediate` (mutation → invalidate dashboard/syncs/remediations).
- **Polling (D-6):** dashboard widgets poll at 30 s (`refetchInterval`); logs/syncs/remediations do not poll (user-driven refetch after mutations). Dashboard `refetchOnWindowFocus` enabled.

### 5.5 Hooks

- `useDebounce(value, 300)`: returns `[raw, debounced]`; `raw !== debounced` drives the "buscando…" indicator; one request per typing burst.
- `useTheme`: `data-theme` + localStorage.
- `useFocusTrap` (fallback only): replicates mock contract — save `document.activeElement`, focus first focusable on open, Tab/Shift+Tab wrap, Escape close, restore focus on close, listener add/remove.

### 5.6 VirtualScroller + keyset integration

Viewport 480 px → ~9 visible rows (page_size default 25 aligns with server contract). Lazy mode: scrolling to the bottom loads the next keyset page (`next_cursor`) and appends; footer page squares use offset `page`/`page_size` derived from `total` and reset scroll on navigation. Zebra rows (odd = `subRowBg`, even = `cardBg`).

### 5.7 Component tree

```
src/
├── main.tsx / App.tsx            # ThemeProvider + PrimeReactProvider + Router
├── app/                          # router.tsx, ThemeProvider.tsx, theme.ts
├── api/                          # client.ts (fetch wrapper, error decode), queries/
├── types/                        # LogEntry, Sync, Archivo, Remediation, DashboardMetrics, Page<T>
├── hooks/                        # useDebounce, useTheme, usePolling, useFocusTrap
├── components/
│   ├── shell/                    # Sidebar, Header, ThemeToggle
│   ├── dashboard/                # KpiCard, ThroughputChart, StatusDistribution, RecentErrors
│   ├── logs/                     # VirtualLogList, LogRow, LogsFooter, StackTraceModal
│   └── syncs/                    # SyncTable (rowExpansion), RemediationTable
├── pages/                        # Dashboard, Logs, Sincronizaciones, Remediacion
└── styles/                       # tokens.css (OKLCH A/B), global.css
```

## 6. DevOps Design

### 6.1 docker-compose.yml

```yaml
networks: { frontend-net, db-net }
volumes:  { pgdata }
services:
  db:       image postgres:16-alpine; healthcheck pg_isready; env POSTGRES_*; volume pgdata; networks [db-net]
  backend:  build ./backend; depends_on db (service_healthy); env DATABASE_URL, POSTGRES_*, CORS_ORIGINS, DB_RETRY_*;
            ports ${BACKEND_PORT}:8000; networks [frontend-net, db-net]      # bridges both
  frontend: build ./frontend; ports ${FRONTEND_PORT}:80; networks [frontend-net]   # db-net unreachable
```

Isolation by construction: frontend attached **only** to `frontend-net`, db **only** to `db-net`, backend bridges both. Frontend never receives `DATABASE_URL` or any DB env. Migrations run from `scripts/up.sh` (exec `alembic upgrade head` in the backend container) — not a compose service.

### 6.2 Dockerfiles

- **backend**: `python:3.12-slim`, non-root user (`appuser`), install from `pyproject.toml`, `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- **frontend**: multi-stage — `node:18-alpine` build (`npm ci` + `npm run build`) → `nginx:alpine` serving `dist/` (SPA fallback to `index.html`). API calls go direct to the backend origin with CORS enabled (devops-docker Req 6); nginx is static-only.

### 6.3 Scripts

| Script | Behavior |
|---|---|
| `scripts/up.sh` | `docker compose build` → `up -d` → wait for db healthy → `docker compose exec backend alembic upgrade head` → optional seed (`SEED=1`) → print URLs. Rerunnable, exit non-zero on failure |
| `scripts/clean.sh` | `docker compose down -v` (removes volumes) |
| `scripts/test.sh` | backend `pytest --cov --cov-fail-under=80` + frontend `vitest run --coverage`; exit non-zero if either fails or coverage < 80 % |

`.env.example` documents: `POSTGRES_USER/PASSWORD/DB`, `DATABASE_URL`, `BACKEND_PORT`, `FRONTEND_PORT`, `CORS_ORIGINS`, `DB_RETRY_INITIAL_BACKOFF`, `DB_RETRY_MAX_ATTEMPTS`, `DB_RETRY_JITTER`, pool params. `.gitignore` excludes `.env` and local artifacts.

### 6.4 Jenkinsfile

Declarative `pipeline { agent any; stages { checkout → lint → unit tests → docker build } }`, fail-fast, no secrets, `post { failure }` optional.
- `checkout`: `checkout scm`.
- `lint`: backend `flake8` + `black --check`; frontend `eslint` — violations fail the stage.
- `unit tests`: `pytest --cov --cov-fail-under=80` (hermetic — Python image with testcontainers, Docker socket available on agent) + `vitest run --coverage` (80 %).
- `docker build`: `docker compose build` (backend + frontend images), no push/deploy.

## 7. Testing Strategy

| Layer | What to test | Approach |
|---|---|---|
| Unit (backend) | Incremental SHA-256 == full-body sha256; checksum mismatch raise; retry/backoff policy (bounded attempts, jitter bounds, monkeypatched clock); error taxonomy mapping | pytest + pytest-asyncio, no DB |
| Integration (backend) | Ingest 201 → replay 200 + `ERR_DUPLICATE_BATCH`; mismatch/malformed/reset → 422 + log row with `correlation_id`, no partial commit; header 422 before body read; fallback correlation_id; dashboard aggregates + zero-fill + clamps; logs keyset walk (every row once), filter composition, detail 404, empty shape; syncs include_files toggle + `archivos_resumen`; remediations POST validation + remediate transitions (RETRY_JOB → running; FORCE_SKIP_VALIDATION → files accepted) | testcontainers-postgres + `alembic upgrade head`; `httpx.AsyncClient` (ASGITransport); per-test DB reset |
| N+1 / perf (backend) | Constant query count on 1,000 rows for dashboard endpoints, syncs, remediations; pool-exhaustion → `ERR_POOL_EXHAUSTED` without hang | SQLAlchemy `event` statement counter; monkeypatched pool acquire |
| Unit (frontend) | `useDebounce`: exactly one request per burst, "buscando…" while raw ≠ debounced | Vitest + RTL, fake timers |
| Component (frontend) | VirtualScroller bounded DOM at scroll offset + `top = idx*56`; focus trap (Escape + focus restore, Tab wrap, overlay click); footer pagination math; theme toggle `data-theme` swap + localStorage; polling refetchInterval | Vitest + RTL (jsdom) |
| Query (frontend) | Dashboard error/loading states with retry affordance; search triggers server query, not client filter | TanStack Query mock |

Strict TDD per `config.yaml` (`apply.tdd: true`): every task writes its failing test first; `scripts/test.sh` is the gate.

## 8. Open Questions Resolved (spec-phase risks)

1. **Frontend coverage gap (Sincronizaciones + Remediación screens)** — **Resolved: fold into this design doc; no new spec.** The `syncs-api` spec already pins the backend contract these screens consume (list with files, remediations history, remediate mutation). Detailed screen requirements are specified here (§5.3 component mapping, §5.7 tree, §5.4 data hooks) and are task-derivable for sdd-tasks. Creating `openspec/specs/frontend-syncs-remediation/spec.md` post-hoc would duplicate the design's job and risk spec/design drift; the design doc is the single authoritative artifact for this phase.
2. **`ejecutada_at` timestamp** — **Confirmed present** in `data-model` spec Req 4: `acciones_remediacion.ejecutada_at TIMESTAMPTZ NOT NULL DEFAULT now()`, indexed on `sincronizacion_id` and `ejecutada_at`. It drives the Remediación "Fecha" column and the `GET /remediations` ordering (`ejecutada_at DESC`, syncs-api Req 2). No schema change needed.
3. **Badge tokens in dark mode (D-4)** — **Decided: dark-mode-adjusted badge palettes (light-on-dark chips) for palette B.** The mock reuses light-theme badge colors in both palettes, but on `bg oklch(17% 0.02 255)` the light palette's text (L ≈ 46–48 %) fails WCAG 2.2 AA (4.5:1) — contrast ≈ 3:1. Design: `statusVisual`/`levelVisual` become token maps with A and B variants; palette B uses saturated dark chip backgrounds (`oklch(30–40% 0.12–0.16 hue)`) with near-white text (L ≥ 90 %). Cost: two extra token rows per badge; no logic change. This deliberately supersedes the proposal's "out of scope: dark-mode badge variants" line (a11y is a project constraint — `accessibility-aa` skill, AA contrast in `config.yaml` context).

## 9. File Tree (deliverable)

```
centinela/
├── .env.example                 # env template (Docker envs, CORS, retry/pool params)
├── .gitignore                   # excludes .env, node_modules, __pycache__, dist, .pytest_cache
├── README.md                    # setup, scripts, architecture overview
├── docker-compose.yml           # db/backend/frontend, frontend-net + db-net, pgdata volume
├── Jenkinsfile                  # checkout → lint → unit tests → docker build
├── scripts/                     # up.sh, clean.sh, test.sh
├── backend/
│   ├── app/                     # api/, core/, db/, models/, schemas/, services/, main.py
│   ├── migrations/              # alembic env.py + versions/0001_initial.py
│   ├── tests/                   # unit/, integration/, conftest.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── src/                     # app/, api/, types/, hooks/, components/, pages/, styles/ (tokens.css)
│   ├── tests/                   # Vitest + RTL
│   ├── index.html, vite.config.ts, tsconfig.json, eslint.config.js, package.json
│   ├── nginx.conf
│   └── Dockerfile               # multi-stage node build → nginx
└── openspec/                    # existing SDD artifacts (specs, changes/, explorations/, config.yaml)
```

## 10. Migration / Rollout

No migration of existing data — greenfield. Single Alembic head creates all tables/enums/indexes; idempotent seed mirrors `plantilla.html` (8 syncs, all 5 estados, 3 tipos, 8 error codes, ≥ 4 remediaciones). Rollback = `scripts/clean.sh` (`docker compose down -v`) + delete change folder / Engram topic.

## 11. Design Decisions Index

| # | Decision | Choice | Alternatives | Rationale |
|---|---|---|---|---|
| D-1 | Retry strategy | Engine-level `retry_acquire()` at connection acquisition | HTTP middleware retry | Middleware can't distinguish safe reads from side-effecting writes; acquisition retry matches mock trace semantics |
| D-2 | Theme tokens | OKLCH → CSS vars (`tokens.css`, `data-theme` A/B) | PrimeReact built-in hex themes | Mock pins exact OKLCH values; overrides keep components token-driven |
| D-3 | Focus trap | PrimeReact `Dialog` built-in; `useFocusTrap` fallback | Custom modal from scratch | Dialog is a11y-tested upstream; apply verifies version behavior, fallback replicates mock contract |
| D-4 | Dark-mode badges | Light-on-dark chips in palette B | Mock fidelity (shared palette) | WCAG 2.2 AA contrast on dark bg; supersedes proposal out-of-scope line |
| D-5 | PrimeReact version | Stable 10.x pinned | v11 alpha | Stability for a technical test; alpha breaks OKLCH override effort |
| D-6 | Dashboard polling | TanStack Query `refetchInterval` 30 s | WebSocket/SSE | Fixed test scope; polling is simple, cacheable, testable with fake timers |

