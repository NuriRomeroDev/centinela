# Frontend Dashboard Specification

## Purpose

React + PrimeReact + TypeScript app replicating plantilla.html: the app shell (sidebar, header, theme toggle, routing) and the Dashboard screen (KPIs, throughput chart, status distribution, recent errors) fed by the dashboard API.

## Requirements

### Requirement 1: App shell layout

The app MUST render the shell from plantilla.html: fixed 248px sidebar (brand block "Centinela / Control & Auditoría", 4 nav items Dashboard/Logs de Errores/Sincronizaciones/Remediación with active state = accent bg + 3px left accent bar, environment card "On-Premise · Prod"), 64px header (screen title + subtitle, theme toggle, avatar "MR"), and a scrollable content area. React Router MUST map / -> Dashboard, /logs, /syncs, /remediacion; the active nav item MUST reflect the route.

#### Scenario: Navigation

- GIVEN the app at "/"
- WHEN the user clicks "Logs de Errores"
- THEN the route changes to /logs, the nav item shows active styling, and the header title/subtitle update per mock

### Requirement 2: Theme toggle (palettes A/B)

The app MUST implement the segmented "Claro/Oscuro" toggle switching between palette A (light) and palette B (dark) OKLCH tokens from exploration section 2.7, applied as CSS variables (tokens.css). All surfaces MUST consume the active tokens (no hard-coded colors). The active segment MUST render with accent bg + white text. Theme selection MAY persist to localStorage.

#### Scenario: Toggle switch

- GIVEN palette A active
- WHEN the user selects "Oscuro"
- THEN CSS variables flip to palette B values (e.g. bg oklch(17% 0.02 255), accent oklch(68% 0.14 250)) and all components re-render with the new tokens

### Requirement 3: Dashboard KPI cards

The Dashboard MUST render 4 KPI cards per mock: label, value (IBM Plex Mono 28px/700), delta with green/red coloring per KPI rule, sub. Values MUST come from GET /dashboard/metrics. Loading and error states MUST render without layout breakage.

#### Scenario: KPI data binding

- GIVEN /dashboard/metrics returns {activas:1, completadas_hoy:3, rechazados:2, tasa:"8.2"}
- WHEN the Dashboard renders
- THEN the 4 cards show those values with mono typography

### Requirement 4: Throughput chart

The Dashboard MUST render "Throughput de lotes · últimos 7 días" from GET /throughput: one bar per day (labels L M X J V S D), accepted = accent bottom bar, rejected = red top bar oklch(68% 0.13 25), normalized to the 140px chart area, legend with 8x8 swatches. MAY use PrimeReact Chart; proportions MUST match the mock.

#### Scenario: Seven-day bars

- GIVEN throughput data for 7 days
- WHEN the card renders
- THEN one bar per day shows stacked accepted/rejected segments with correct labels

### Requirement 5: Status distribution

The Dashboard MUST render "Distribución de estados" from GET /status-distribution: per-estado row with label, count (mono), and a 6px progress bar filled with the status color (statusVisual), width proportional to pct.

#### Scenario: Distribution bars

- GIVEN distribution [{estado:"completed", count:4, pct:50}, ...]
- WHEN the card renders
- THEN each row shows count and a bar of width proportional to pct

### Requirement 6: Recent errors list

The Dashboard MUST render "Actividad reciente de errores" from GET /logs/recent?limit=5: 5 rows with level dot (levelVisual text color), code (mono, 150px), message ellipsized, timestamp; "Ver todos ->" navigates to /logs; clicking a row MUST navigate to /logs AND open the stack-trace modal for that log (modal contract in frontend-logs-virtualization).

#### Scenario: Row click navigation

- GIVEN a recent error row
- WHEN the user clicks it
- THEN the app navigates to /logs and the modal opens with that log's details

### Requirement 7: Data fetching

All dashboard data MUST be fetched with TanStack Query against the /api/v1 client; queries MUST support refetch and cache invalidation; the four widgets MUST use the documented dashboard-api endpoints.

#### Scenario: Fetch failure

- GIVEN the API returns 500
- WHEN the Dashboard mounts
- THEN each widget renders an error state with a retry affordance and no unhandled exceptions

## Acceptance Criteria

- Shell + routing + 4 nav items replicate mock dimensions and active state
- Theme toggle flips all OKLCH tokens A<->B; no hard-coded colors in components
- Dashboard widgets bind to the API and match mock layout/typography
- Recent-errors row click -> /logs + modal open; "Ver todos ->" -> /logs
- Loading/error/empty states render cleanly
