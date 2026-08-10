# Centinela — Control & Auditoría

Plataforma de monitoreo de sincronizaciones y errores de ingestión: backend FastAPI (`backend/`) + frontend React/PrimeReact (`frontend/`).

## Frontend

Aplicación SPA en `frontend/` que replica `plantilla.html`: shell fijo (sidebar 248px + header 64px), Dashboard con polling, logs virtualizados con búsqueda debounced y modal de stack trace con focus trap.

### Stack

- Vite + React 18 + TypeScript `strict`
- PrimeReact **10.9.8** (pin fijo, línea estable 10.x) + PrimeIcons 7
- TanStack Query v5, react-router-dom v6, chart.js
- Vitest + Testing Library (jsdom)

### Scripts

```bash
cd frontend
npm install        # usa registry público vía .npmrc (el token CodeArtifact global no aplica)
npm run dev        # Vite dev server, proxy /api -> http://localhost:8000
npm test           # vitest run
npm run test:coverage  # vitest con umbral de cobertura ≥80 %
npm run lint       # eslint
npm run build      # tsc --noEmit && vite build
```

### Arquitectura

```
src/
├── app/            # router.tsx, ThemeProvider, theme.ts (claves de tema)
├── api/            # client.ts (fetch wrapper, ApiError) + queries/ (hooks TanStack Query)
├── types/          # contratos de la API (LogEntry, Sync, Remediation, Page<T>…)
├── hooks/          # useDebounce (nativo, sin lodash), useTheme, usePolling, useFocusTrap
├── components/
│   ├── shell/      # Sidebar, Header, ThemeToggle
│   ├── dashboard/  # KpiCard, ThroughputChart, StatusDistribution, RecentErrors
│   ├── logs/       # VirtualLogList (VirtualScroller), LogRow, LogsFooter, StackTraceModal
│   └── syncs/      # SyncTable (rowExpansion), RemediationTable
├── pages/          # Dashboard, Logs, Sincronizaciones, Remediacion
└── styles/         # tokens.css (OKLCH A/B) + global.css
```

### Tema

- Tokens OKLCH en `styles/tokens.css`: paleta A en `:root`, paleta B en `:root[data-theme='b']`; el toggle Claro/Oscuro escribe `data-theme` en `<html>` y persiste en `localStorage` (`centinela-theme`).
- PrimeReact 10.9.8 **no expone variables `--p-*`** (sus temas lara hardcodean hex); el remapeo de tokens se hace con overrides por clase en `tokens.css` (`.p-inputtext`, `.p-dialog*`, `.p-datatable`, `.p-tag`, `.p-toast`). Los componentes de la app consumen exclusivamente `var(--token)` — cero colores hardcodeados.
- Badges de nivel/estado (`levelVisual`/`statusVisual`, decisión D-4): variantes A y B por token; en B son chips oscuros saturados con texto casi blanco (WCAG 2.2 AA, ≥4.5:1 verificado).

### Criterios de evaluación implementados

| Criterio | Implementación | Tests |
|---|---|---|
| Dashboard con polling eficiente | `usePolling`/queries con `refetchInterval` 30s + `refetchOnWindowFocus` | `src/hooks/usePolling.test.tsx`, `src/pages/Dashboard.test.tsx` |
| Debounce nativo 300ms (sin lodash) | `useDebounce` con `setTimeout`/`clearTimeout` | `src/hooks/useDebounce.test.tsx` |
| VirtualScroller (56px / 480px / overscan 4) + keyset | `VirtualLogList` + `getWindow` | `src/components/logs/virtualWindow.test.ts`, `VirtualLogList.test.tsx` |
| Focus trap en modal stack trace | `useFocusTrap` (Tab wrap, Escape, restauración de foco) | `src/hooks/useFocusTrap.test.tsx`, `StackTraceModal.test.tsx` |

## Backend

API FastAPI + SQLAlchemy async + PostgreSQL (tests de integración con testcontainers). Ver `backend/` y `openspec/` para el contrato de endpoints.
