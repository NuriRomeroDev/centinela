# Exploration: Plataforma Centinela

> Banking reconciliation & idempotency control platform — fullstack technical test delivery.
> Explored: reference UI (`plantilla.html`, byte-identical to `Centinela Dashboard - PrimeReact.dc.html`),
> openspec config (`openspec/config.yaml`), technical-test backend/DevOps requirements.
> Status: **ready for proposal**. No application code exists — greenfield.

---

## 1. Executive Summary

Centinela is a greenfield fullstack delivery with a fixed technical-test scope: a React + PrimeReact
dashboard (replicating the `plantilla.html` mock "Centinela Dashboard"), a FastAPI (async) backend with
SHA-256 idempotency, a PostgreSQL schema of 4 tables, and a dockerized topology with network isolation
plus a declarative Jenkinsfile. The reference mock is **already PrimeReact-targeted** (confirmed: the
file given as reference is byte-identical to the `PrimeReact.dc.html` variant), so the design maps
1:1 onto PrimeReact components (`VirtualScroller`, `DataTable` with `rowExpansion`, `Dialog`, `Chart`,
`InputText`, `Badge/Tag`) rather than requiring custom UI primitives.

Exploration scope: map every UI surface + design token from the mock, propose the API surface needed to
power it, map the fixed data model, and propose the monorepo layout + DevOps topology. No code written.

---

## 2. UI Component Inventory (from `plantilla.html`)

### 2.1 Layout shell

| Element | Spec |
|---|---|
| Root | `display:flex; height:100vh; width:100vw; overflow:hidden` — app shell, IBM Plex Sans, bg=`tok.bg`, color=`tok.textPrimary` |
| Sidebar | Fixed `248px` wide, `flex-shrink:0`, `padding:20px 14px`, bg=`tok.sidebarBg`, right border `1px tok.sidebarBorderCss` |
| Brand block | 32×32 rounded (8px) square, `tok.accent` bg, white bold "C"; text "Centinela" (14.5px/700, `tok.sidebarBrand`) over "Control & Auditoría" (10.5px uppercase, letter-spacing 0.4px, `tok.sidebarSub`); divider below |
| Nav items (4) | Dashboard `◧`, Logs de Errores `⚠`, Sincronizaciones `⇄`, Remediación `✓`. 13.5px/500, padding `10px 12px`, radius 6px, active = `tok.navActiveBg` bg + `tok.navActiveText` + 3px left bar `tok.accent`; hover = `tok.trackBg` |
| Environment card | Bottom of sidebar (`flex:1` spacer above): 12px padding, radius 10px, `tok.sidebarFootBg`, green status dot `oklch(58% 0.1 155)`, "On-Premise · Prod" |
| Header | `height:64px`, `padding:0 28px`, bottom border `tok.cardBorder`, bg `tok.headerBg`; screen title 17px/700 + subtitle 12px (`tok.textSecondary`) |
| Theme toggle | Segmented control: track `tok.toggleTrack` radius 8px padding 3px; options "☀ Claro" / "☾ Oscuro" (11.5px/600); active segment = `tok.accent` bg + white text. Switches palette A/B |
| Avatar | 34px circle, bg `tok.avatarBg`, text `tok.avatarText`, initials "MR" |
| Content area | `padding:26px 28px 40px; overflow-y:auto` |

### 2.2 Dashboard screen

| Component | Spec |
|---|---|
| KPI cards (4) | Grid `repeat(4,1fr)`, gap 16px, margin-bottom 22px. Card: `tok.cardBg`, 1px `tok.cardBorder`, radius 12px, padding `18px 20px`, `fadeIn 0.4s`. Label 12px `tok.textSecondary`; value **28px/700 IBM Plex Mono**; delta 12px/600 colored (accent green `oklch(40% 0.1 155)` / red `oklch(46% 0.16 25)`); sub 11.5px secondary |
| KPIs | ① Sincronizaciones activas (= estado `running`) ② Completadas hoy (= `completed` today) ③ Archivos rechazados (= sum of rejected files) ④ Tasa de errores críticos (= CRITICAL logs / total logs %) |
| Throughput card | Grid `1.4fr 1fr` row. Title "Throughput de lotes · últimos 7 días" 13.5px/600. Bars: 7 days (labels L M X J V S D), height 140px; accepted = `tok.accent` bottom bar, rejected = `oklch(68% 0.13 25)` top bar (radius `4px 4px 0 0`). Legend 11.5px with 8×8 swatches |
| Distribución de estados | Title 13.5px/600. Rows: label + count (mono), 6px progress bar (radius 3px, `tok.trackBg` track), fill = status color |
| Recent errors (5) | Rows 11px vertical padding, bottom border `tok.rowBorder`; 7px dot (level color), code mono 11.5px width 150px, message 12.5px ellipsis flex:1, timestamp 11.5px. Row click → **navigates to Logs screen AND opens the modal** (mock behavior). Header has "Ver todos →" link (`tok.accent`) |

### 2.3 Logs screen

| Component | Spec |
|---|---|
| Search | Input flex:1 max-width 420px, padding `10px 14px 10px 36px`, radius 6px, border `tok.cardBorder`, bg `tok.cardBg`, 13px. Focus: `border-color: tok.accent; box-shadow: 0 0 0 2px tok.focusRing`. Magnifier glyph absolute left 12px. Placeholder: "Buscar por mensaje, código o servicio…" |
| Debounce | **Native 300ms** (`setTimeout`/`clearTimeout`), NO lodash. `searchRaw` vs `searchDebounced`; "buscando…" indicator while pending |
| Filter fields | `mensaje`, `codigo_error`, `servicio_responsable` (case-insensitive contains) |
| List header | Grid `90px 130px 1fr 120px 110px`, `padding:13px 18px`, bg `tok.trackBg`, 11px/700 uppercase: Nivel · Código · Mensaje · Servicio · Fecha |
| Virtualized list | Viewport `height:480px; overflow-y:auto; position:relative`. Spacer `height = rows × ROW_H`. **ROW_H = 56px, OVERSCAN = 4**; `startIdx = max(0, floor(scrollTop/ROW_H) − OVERSCAN)`; `visCount = ceil(480/56) + 2×OVERSCAN`; rows `position:absolute; top = idx×56px; height:56px`; zebra rows (odd = `tok.subRowBg`, even = `tok.cardBg`) |
| Level badge | 10.5px/700, padding `3px 8px`, radius 5px, bg/text from `levelVisual(nivel)` |
| Pagination footer | Left: "Mostrando **1–9** de N" (11.5px). Right: page squares 26×26 radius 6px (`‹ 1 2 ›`); active page = `tok.accent` bg white text |

### 2.4 Sincronizaciones screen

| Component | Spec |
|---|---|
| Header grid | `24px 170px 100px 110px 140px 150px 170px 1fr` (Chevron · Correlation ID · Estado · Fecha · Iniciado · Finalizado · Usuario · Archivos), 11px/700 uppercase on `tok.trackBg` |
| Expandable rows | Row click toggles. Chevron `▸` rotates `rotate(90deg)` (transform + `transition:transform 0.15s`). Estado badge from `statusVisual`. Correlation ID mono 11.5px. Archivos column summary: `"N total · M rechazados"` |
| Expanded sub-row | bg `tok.subRowBg`, padding `14px 18px 18px 46px`; label "Archivos procesados" 11px uppercase; file rows grid `1.4fr 110px 1.6fr 110px 100px` (nombre · tipo badge · checksum mono · estado badge · registros mono) |

### 2.5 Remediación screen

| Component | Spec |
|---|---|
| Table | Header grid `150px 170px 1fr 150px 100px 1.4fr` (Fecha · Sincronización · Acción · Ejecutado por · Resultado · Notas), 11px/600 uppercase. Action pill: 11px/600, padding `4px 9px`, radius 6px, `tok.tagBg`. Resultado badge from `statusVisual` (success/failed). Notas ellipsis |

### 2.6 Stack-trace modal (focus trap)

| Component | Spec |
|---|---|
| Overlay | `position:fixed; inset:0; background:rgba(15,23,42,0.55); z-index:100`, `overlayIn 0.15s`; click overlay closes (`onMouseDown` on overlay, stopPropagation on dialog) |
| Dialog | `width:640px; max-height:80vh`, flex column, bg `tok.cardBg`, radius 14px, shadow `0 24px 60px rgba(0,0,0,0.3)`, `role="dialog" aria-modal="true"` |
| Header | Level badge + code mono 14px/700 + close button `✕` 30×30 radius 7px, `aria-label="Cerrar"` |
| Body | Message 13.5px `line-height:1.5`; metadata grid 2 cols (Correlation ID mono · Servicio · Registrado, 10.5px uppercase labels); "Stack trace" label; `<pre>` bg `tok.traceBg` / text `tok.traceText`, mono 11.5px `line-height:1.6`, padding 16px, radius 9px, `white-space:pre-wrap`, `overflow-x:auto` |
| Footer | "Cerrar (Esc)" ghost button + "Reintentar job" accent button (both close in mock) |
| **Focus trap** | On open: save `document.activeElement`, focus first focusable inside after mount. On close: restore focus to trigger. `Tab` cycles, `Shift+Tab` wraps (first↔last), `Escape` closes. Event listener added/removed with open/close |

### 2.7 Design tokens (OKLCH) — theme contract for the React theme

**Palette A (Claro):**

| Token | Value |
|---|---|
| `bg` | `oklch(97.3% 0.004 250)` |
| `sidebarBg` | `oklch(23% 0.045 255)` |
| `sidebarDivider` | `oklch(100% 0 0 / 0.09)` |
| `sidebarBrand` / `sidebarSub` | `oklch(96% 0.004 250)` / `oklch(58% 0.03 250)` |
| `sidebarFootBg` | `oklch(100% 0 0 / 0.04)` |
| `navText` / `navActiveBg` / `navActiveText` | `oklch(70% 0.025 250)` / `oklch(60% 0.09 250 / 0.18)` / `oklch(85% 0.04 250)` |
| `accent` | `oklch(42% 0.11 255)` (blue) |
| `headerBg` / `cardBg` | `oklch(99% 0.002 250)` |
| `cardBorder` / `rowBorder` | `oklch(90% 0.006 250)` / `oklch(93.5% 0.004 250)` |
| `textPrimary` / `textSecondary` | `oklch(22% 0.015 255)` / `oklch(49% 0.015 255)` |
| `trackBg` / `tagBg` / `subRowBg` | `oklch(92.5% 0.006 250)` / `oklch(94% 0.008 250)` / `oklch(96% 0.004 250)` |
| `toggleTrack` / `avatarBg` / `avatarText` | `oklch(92.5% 0.006 250)` / `oklch(23% 0.045 255)` / `oklch(85% 0.04 250)` |
| `traceBg` / `traceText` | `oklch(23% 0.045 255)` / `oklch(85% 0.01 250)` |
| `focusRing` | `oklch(42% 0.11 255 / 0.18)` |

**Palette B (Oscuro):**

| Token | Value |
|---|---|
| `bg` / `sidebarBg` | `oklch(17% 0.02 255)` / `oklch(13% 0.022 255)` |
| `sidebarDivider` | `oklch(100% 0 0 / 0.08)` |
| `sidebarBrand` / `sidebarSub` | `oklch(95% 0.004 255)` / `oklch(58% 0.02 255)` |
| `navText` / `navActiveBg` / `navActiveText` | `oklch(65% 0.02 255)` / `oklch(68% 0.14 250 / 0.2)` / `oklch(85% 0.06 250)` |
| `accent` | `oklch(68% 0.14 250)` (brighter blue) |
| `headerBg` / `cardBg` / `cardBorder` / `rowBorder` | `oklch(19% 0.02 255)` / `oklch(20% 0.02 255)` / `oklch(28% 0.02 255)` / `oklch(25% 0.02 255)` |
| `textPrimary` / `textSecondary` | `oklch(93% 0.004 255)` / `oklch(64% 0.015 255)` |
| `trackBg` / `tagBg` / `subRowBg` | `oklch(24% 0.02 255)` / `oklch(26% 0.02 255)` / `oklch(22% 0.02 255)` |
| `toggleTrack` / `avatarBg` / `avatarText` | `oklch(24% 0.02 255)` / `oklch(68% 0.14 250)` / `oklch(14% 0.02 255)` |
| `traceBg` / `traceText` | `oklch(10% 0.02 255)` / `oklch(85% 0.01 255)` |
| `focusRing` | `oklch(68% 0.14 250 / 0.25)` |

**Status visual** (`statusVisual` — shared by both palettes in mock; RE-CHECK in proposal: mock renders light-themed badge colors in both modes):

| Status | bg / text |
|---|---|
| `pending` | `oklch(93% 0.008 255)` / `oklch(48% 0.02 255)` |
| `running` | `oklch(90% 0.09 252)` / `oklch(46% 0.19 258)` |
| `completed` | `oklch(90% 0.11 155)` / `oklch(41% 0.16 155)` |
| `failed` | `oklch(91% 0.13 25)` / `oklch(48% 0.21 25)` |
| `rejected` | `oklch(90% 0.14 70)` / `oklch(46% 0.15 62)` |
| `accepted` / `success` | same as `completed` (green) |

**Level visual** (`levelVisual`): WARNING `oklch(90% 0.14 70)`/`oklch(46% 0.15 62)` (amber) · ERROR `oklch(89% 0.15 45)`/`oklch(47% 0.19 40)` (orange) · CRITICAL `oklch(90% 0.13 25)`/`oklch(47% 0.22 25)` (red).

**Typography:** IBM Plex Sans 400/500/600/700 (UI), IBM Plex Mono 400/500/600 (values, codes, timestamps, checksums). Google Fonts import. Scrollbar: 8px, thumb `#CBD5E1` (webkit — mock only).

### 2.8 Mock data insights (realistic domain seeds)

- Error codes (seed for logs + backend error taxonomy): `ERR_CHECKSUM_MISMATCH` (ERROR), `ERR_DB_TIMEOUT` (CRITICAL), `ERR_SCHEMA_VALIDATION` (WARNING), `ERR_DUPLICATE_BATCH` (WARNING — idempotent replay), `ERR_NETWORK_RESET` (ERROR), `ERR_ORPHAN_RECORD` (ERROR), `ERR_JSON_MALFORMED` (CRITICAL), `ERR_POOL_EXHAUSTED` (CRITICAL).
- `servicio_responsable` seeds: `API_Gateway`, `Validation_Engine`, `Data_Worker`, `DB_Connection_Pool`.
- Tracebacks reference real app modules (`app/services/idempotency.py`, `app/db/session.py`, `app/parsers/payload.py`, `app/workers/data_worker.py`) — useful naming hints for backend structure.
- Sync usuarios: `svc.batch.ops`, `j.medina`; remediation actores: `j.medina`, `a.rojas`, `svc.autoheal`; actions: `RETRY_JOB`, `FORCE_SKIP_VALIDATION`, `MANUAL_REQUEUE`, `PURGE_DUPLICATE`.
- File naming: `lote_{tipo}_{fecha}_{n}.csv`, tipos `ventas|inventario|clientes`.

---

## 3. Backend API Surface Proposal (to power the UI)

All responses JSON. Prefix `/api/v1`. FastAPI async; Pydantic v2 schemas.

| Endpoint | Method | Purpose | Powering UI |
|---|---|---|---|
| `/api/v1/dashboard/metrics` | GET | KPIs: active syncs (`running`), completed today, rejected files count, critical error rate | Dashboard KPI cards |
| `/api/v1/throughput?days=7` | GET | Daily accepted/rejected counts (last 7 days) | Throughput chart |
| `/api/v1/status-distribution` | GET | Count + % per estado | Distribución de estados |
| `/api/v1/logs/recent?limit=5` | GET | Latest 5 error logs | Recent errors list |
| `/api/v1/logs?search=&page=&page_size=` | GET | Filtered (mensaje/codigo/servicio, case-insensitive contains) + paginated logs; return `total`, `items`, `page`, `page_size` | Logs screen (search + virtualized list + footer pagination) |
| `/api/v1/logs/{id}` | GET | Single log incl. full `stack_trace` (detail could be inlined to avoid second roundtrip — DECISION in proposal) | Stack-trace modal |
| `/api/v1/syncs?include_files=true` | GET | Syncs with files (SQLAlchemy `selectinload` — N+1 mitigation required) | Sincronizaciones screen + expandable files |
| `/api/v1/remediations` | GET | List of manual actions | Remediación screen |
| `/api/v1/remediations` | POST | Record manual action (accion_ejecutada, ejecutado_por, resultado, notas) | "Reintentar job" / future actions |
| `/api/v1/ingest` | POST | File/batch upload with **idempotency** (see §3.1) | Backend core (no direct UI control in mock) |

Design notes:
- Dashboard metrics could be one aggregate endpoint vs. the 4 split ones above — **DECISION for proposal** (mock renders 4 distinct widgets; one aggregate endpoint reduces roundtrips but complicates caching).
- Logs list MUST support server-side filtering + pagination for scale; the 480px/56px virtualization is then a pure client rendering concern (VirtualScroller), with pagination done by the API (page squares in footer).

### 3.1 Idempotency contract (from technical test — fixed)

- SHA-256 checksum computed over payload; **unique** on `archivos_procesados.checksum` (DB-level guard).
- Duplicate submit → return the **original result** with HTTP 200 (idempotent replay), log `ERR_DUPLICATE_BATCH` WARNING (per mock trace).
- Checksum mismatch (client-supplied vs server-computed) → structured error log w/ `correlation_id` + clean HTTP 422 (`ERR_CHECKSUM_MISMATCH`).
- Corrupted/malformed payload (`ERR_JSON_MALFORMED` / `ERR_SCHEMA_VALIDATION`) → structured error log + 422.
- CPU-heavy work → offloaded to executors/threads so the async event loop never blocks.
- PostgreSQL outage → connection-pool-level retry policy: exponential backoff + jitter; retry must never hang HTTP requests (bounded waits / fail fast with `ERR_DB_TIMEOUT` / `ERR_POOL_EXHAUSTED` structured error).

---

## 4. Data Model Mapping Notes

Fixed schema (4 tables) → maps 1:1 to SQLAlchemy 2.x ORM models. Enums via `enum` PG types (SQLAlchemy `Enum` w/ `native_enum=True` or check-constrained strings — DECISION for proposal).

| Table | Columns | Notes / UI mapping |
|---|---|---|
| `sincronizaciones` | `id UUID PK` · `correlation_id UUID UNIQUE (indexed)` · `fecha_ejecucion date` · `estado enum pending/running/completed/failed/rejected` · `iniciado_at` · `finalizado_at nullable` · `usuario_origen varchar(100)` | UI estado badge = `statusVisual(estado)`; "Completadas hoy" filters `fecha_ejecucion = today`; KPIs derive from estado |
| `archivos_procesados` | `id serial PK` · `sincronizacion_id FK→sincronizaciones CASCADE` · `nombre_archivo varchar(255)` · `tipo_archivo enum ventas/inventario/clientes` · `checksum varchar(64) UNIQUE` · `estado enum accepted/rejected` · `registros_totales int default 0` · `datos_payload JSONB nullable` | Idempotency guard = unique checksum; expandable files sub-rows; "archivos rechazados" KPI = count estado=rejected |
| `logs_errores` | `id serial PK` · `correlation_id FK→sincronizaciones.correlation_id CASCADE (indexed)` · `servicio_responsable varchar(100)` · `nivel_error enum WARNING/ERROR/CRITICAL` · `codigo_error varchar(50)` · `mensaje text` · `stack_trace text nullable` · `creado_at default now()` | Logs screen rows + modal; level badge = `levelVisual`; search fields map to columns |
| `acciones_remediacion` | `id serial PK` · `sincronizacion_id FK CASCADE` · `accion_ejecutada varchar(100)` · `ejecutado_por varchar(100) NOT NULL` · `resultado enum success/failed` · `notas text nullable` | Remediación table; `resultado` badge = `statusVisual(success/failed)` |

Additional mapping notes:
- `logs_errores.correlation_id` FK references `sincronizaciones.correlation_id` (not PK) — keep composite/unique index on `sincronizaciones.correlation_id` to support the FK.
- Migrations: Alembic recommended (runs in `up.sh`); or a SQL init script mounted to the postgres container — DECISION for proposal (Alembic is the maintainable default).
- Seed data for demo parity with the mock (syncs/files/logs/remediations + the 8 error codes) — optional seed script for dev/test.
- Rejected-file counts and the "N total · M rechazados" sync summary can be derived server-side (aggregates) to avoid client aggregation over full datasets.

---

## 5. DevOps Topology

### 5.1 docker-compose services & networks

```
networks:
  frontend-net:   # frontend + backend (frontend reaches backend ONLY)
  db-net:         # db + backend (frontend has NO access — isolation requirement)
services:
  db:       postgres:16-alpine, healthcheck pg_isready, volume for data, attached to db-net
  backend:  FastAPI + uvicorn, attached to BOTH frontend-net AND db-net (bridge), depends_on db healthy, env from .env
  frontend: nginx serving built React (or Vite dev), attached to frontend-net ONLY, published port 80/5173
```

- Isolation guarantee: `frontend` container is attached **only** to `frontend-net`; `db` only to `db-net`; `backend` bridges both. Frontend cannot reach the DB network by construction.
- `.env.example` at repo root: `POSTGRES_USER/PASSWORD/DB`, `DATABASE_URL`, `BACKEND_PORT`, `FRONTEND_PORT`, retry params (initial backoff, max attempts, jitter), `CORS_ORIGINS`.

### 5.2 Scripts (per technical test)

| Script | Behavior |
|---|---|
| `scripts/up.sh` | `docker compose build` + `up -d` + wait for db healthy + run migrations (alembic upgrade head) |
| `scripts/clean.sh` | `docker-compose down -v` (volumes removed) |
| `scripts/test.sh` | Backend: `pytest --cov --cov-fail-under=80` (in container or host) + Frontend: `npm test` / `vitest run --coverage` — aligns with openspec `testing` block |

### 5.3 Jenkinsfile (declarative stages)

1. `checkout` — SCM
2. `lint` — backend: `flake8` + `black --check`; frontend: `eslint` (per config.yaml/technical test)
3. `unit tests` — `pytest` with **80% coverage minimum** (`--cov-fail-under=80`) + frontend `vitest run --coverage` (80% threshold)
4. `docker build` — build backend + frontend images (compose build)

Note: no deploy/publish stage in scope (technical test stops at build).

---

## 6. Monorepo Layout Proposal

```
centinela/
├── openspec/                  # SDD artifacts (existing — config.yaml, specs/, changes/, explorations/)
├── .atl/skill-registry.md     # existing skill registry (do not touch)
├── .gitignore
├── .env.example
├── README.md                  # setup, scripts, architecture overview
├── docker-compose.yml
├── Jenkinsfile
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app factory + CORS + routers
│   │   ├── api/               # routers: dashboard.py, logs.py, syncs.py, remediations.py, ingest.py
│   │   ├── core/              # settings (pydantic-settings), logging config
│   │   ├── db/                # engine/session w/ retry pool (backoff+jitter), Base
│   │   ├── models/            # sincronizaciones, archivos_procesados, logs_errores, acciones_remediacion
│   │   ├── schemas/           # pydantic response/request models
│   │   └── services/          # idempotency.py (SHA-256 guard), checksum.py, ingest.py, metrics.py
│   ├── migrations/            # Alembic (env.py, versions/)
│   ├── tests/                 # pytest + pytest-asyncio (unit; testcontainers or sqlite for DB tests — DECISION)
│   ├── pyproject.toml         # deps, flake8/black config, pytest config
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.tsx / App.tsx
│   │   ├── app/               # router, PrimeReact theme provider, palette A/B tokens (OKLCH CSS vars)
│   │   ├── api/               # TanStack Query hooks (useDashboardMetrics, useLogs, useSyncs, useRemediations)
│   │   ├── types/             # LogEntry, Sync, Archivo, Remediation, DashboardMetrics
│   │   ├── components/        # presentational: KpiCard, ThroughputChart, StatusDistribution, RecentErrors, VirtualLogList, SyncTable, RemediationTable, StackTraceModal, Sidebar, Header, ThemeToggle
│   │   ├── pages/             # Dashboard, Logs, Sincronizaciones, Remediación
│   │   ├── hooks/             # useDebounce (native 300ms), useTheme, useFocusTrap
│   │   └── styles/            # tokens.css (OKLCH palettes A/B), global.css
│   ├── tests/                 # Vitest + React Testing Library (debounce, virtualization, focus trap, query hooks)
│   ├── package.json / vite.config.ts / tsconfig.json / eslint.config.js
│   └── Dockerfile             # build → nginx (or vite dev target)
└── scripts/
    ├── up.sh
    ├── clean.sh
    └── test.sh
```

Validation against requirements:
- **Testing** ✓ — `backend/tests` (pytest + pytest-asyncio) and `frontend/tests` (Vitest + RTL) exist at the top of each app; `scripts/test.sh` runs both; strict_tdd respected by per-suite commands in `openspec/config.yaml`.
- **Docker isolation** ✓ — compose networks map cleanly onto the layout; frontend/backend/db services each have a Dockerfile or image.
- **Lint gates** ✓ — `pyproject.toml` carries flake8/black; frontend carries ESLint config; Jenkinsfile consumes them.
- **Idempotency/retry code** ✓ — isolated in `backend/app/services/idempotency.py` + `backend/app/db/` retry pool, unit-testable in isolation.

---

## 7. Open Questions / Risks

1. **Ingest transport** (HIGH — must be resolved in proposal): how does the client send the payload?
   - (a) `multipart/form-data` file field + metadata fields (simple, browser-friendly), checksum computed server-side on received bytes, OR
   - (b) raw body + `X-Checksum-SHA256` / `X-Correlation-ID` headers (matches the `ERR_CHECKSUM_MISMATCH` "expected vs actual" semantics — client-supplied expected checksum), OR
   - (c) JSON envelope `{ correlation_id, nombre_archivo, tipo_archivo, checksum, payload }`.
   - Mock tracebacks reference `stream_upload` + `read(8192)` chunks → suggests raw streaming with headers (b). Needs a decision in proposal.
2. **correlation_id origin**: client-generated (allows true retry-replay with same ID; unique index backs it) vs server-generated (simpler, but client can't pre-link retries). Mock's `ERR_DUPLICATE_BATCH` trace mentions "Returning cached response for correlation_id" → implies client-supplied. DECISION needed.
3. **Logs pagination vs virtualization**: mock paginates client-side over 38 rows; production needs server-side pagination. Does the footer paginator page through the API (`page`/`page_size`) with VirtualScroller rendering the current page, or does the API return everything and client virtualizes? DECISION for proposal (recommend: API paginated + VirtualScroller per page).
4. **Status/level badge tokens in dark mode**: mock reuses light-theme badge colors in palette B — is that intentional (kept as-is for fidelity) or should the proposal derive dark-mode variants? (a11y contrast risk on dark bg).
5. **Modal "Reintentar job"**: mock button only closes the modal. Real behavior = POST `/api/v1/remediations` (RETRY_JOB) and/or re-trigger ingest? Scope decision.
6. **Dashboard aggregate vs split endpoints**: one `/dashboard/metrics` aggregate vs 4 dedicated endpoints. Trade-off: roundtrips vs. cache granularity.
7. **"Completadas hoy" definition**: calendar day vs rolling 24h vs last `fecha_ejecucion` — affects the KPI SQL.
8. **DB testing strategy**: `testcontainers-postgres` (real PG, honors enums/JSONB/FKs) vs SQLite (fast but enum/JSONB drift). Given the test is PG-specific, testcontainers is safer; adds Docker dependency to `test.sh`.
9. **Theme persistence**: toggle state in `localStorage` (mock doesn't persist — flag as product decision).
10. **PrimeReact version pinning**: latest stable (v10.x line) vs alpha (v11.0.0-alpha) — pin stable; OKLCH tokens via PrimeReact `primereact/resources/themes` + CSS variable overrides (PrimeReact themes use hex by default — the OKLCH palette must be injected as design tokens, which may require overriding PrimeReact's Sass/CSS vars; effort note for proposal).
11. **Alembic vs SQL init script** for migrations in `up.sh`.
12. **CORS**: frontend on a separate network/port → backend must allow CORS from the frontend origin (dev and prod).

---

## 8. Affected Areas

Greenfield — no application code exists. Affected = everything to be created:
- `backend/` — FastAPI app, models, idempotency service, retry pool, tests
- `frontend/` — React + Vite + PrimeReact app replicating the mock (components, tokens, hooks, tests)
- `docker-compose.yml`, `scripts/{up,clean,test}.sh`, `Jenkinsfile`, `.env.example`, `README.md`
- `openspec/` — this exploration + downstream SDD artifacts (proposal/spec/design/tasks)

## 9. Recommendation

Proceed to **sdd-propose** with the monorepo layout in §6, the API surface in §3, and the idempotency/retry contract in §3.1 as the proposal baseline. Resolve open questions 1–3 (ingest transport, correlation_id origin, logs pagination strategy) during proposal — they are the only scope-defining unknowns; everything else is fixed by the technical test.

## 10. Ready for Proposal

**Yes.** The reference UI, data model, backend contract, and DevOps topology are fully mapped. The proposal phase must lock: ingest transport (multipart vs raw+headers), correlation_id generation side, and logs pagination strategy.
