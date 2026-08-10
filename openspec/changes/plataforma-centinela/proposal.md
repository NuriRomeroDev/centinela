# Proposal: Plataforma Centinela — Fullstack Technical Test Delivery

## Intent
Deliver the fixed-scope technical test "Centinela": React + PrimeReact dashboard (replicating `plantilla.html`), FastAPI async backend (SHA-256 idempotency), PostgreSQL 4-table schema, dockerized isolation, Jenkinsfile.

## Scope
### In Scope
- Monorepo: `backend/`, `frontend/`, `docker-compose.yml`, `scripts/{up,clean,test}.sh`, `Jenkinsfile`, `README.md`, `.env.example`
- Ingest idempotency; dashboard/logs/syncs/remediations APIs; migrations + seed
- pytest + pytest-asyncio (testcontainers) & Vitest + RTL, ≥80% coverage each
### Out of Scope
- Real auth; prod deploy/CI publish; E2E browser tests; dark-mode badge variants

## Capabilities (new — sdd-spec contract)
- `data-model`: 4 tables, enums, UUIDs, checksum
- `ingest-idempotency`: raw-bytes ingest, SHA-256, replay, 422
- `dashboard-api`: metrics, throughput, status, recent logs
- `logs-api`: search, keyset paging, detail
- `syncs-remediation-api`: syncs + files, remediations
- `frontend-shell`: layout, OKLCH A/B toggle, routing
- `frontend-dashboard`: KPIs, chart, status bars, recent errors
- `frontend-logs`: VirtualScroller, debounce, paging, focus trap
- `frontend-syncs-remediation`: expandable rows, remediation
- `devops-delivery`: networks, scripts, Jenkinsfile

## Approach
Stack: FastAPI/SQLAlchemy2/asyncpg/Pydantic2 · React18/Vite/PrimeReact · testcontainers · pytest-asyncio · Vitest+RTL. Layout per exploration §6; APIs per §3. Locked decisions:
1. **Raw bytes + headers** (`X-Correlation-Id`, `X-File-Name`, `X-Tipo-Archivo`, `X-Checksum-SHA256`): incremental SHA-256 over streamed chunks; header = expected checksum → mismatch = 422 + log row. Multipart can't verify raw stream; JSON base64-inflates +33%.
2. **Client-supplied correlation_id** (idempotency key), server fallback when absent; duplicate → original 200 + `ERR_DUPLICATE_BATCH` warning.
3. **Server-side keyset pagination** on serial `logs_errores.id` (newest-first, `id < cursor`); VirtualScroller renders page (56px rows, overscan 4); footer pages via API.

## Affected Areas
| Area | Impact |
|------|--------|
| `backend/`, `frontend/`, root configs/scripts | New (greenfield) |
| `openspec/specs/*` | New (10 specs) |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DB outage hangs HTTP | Med | Bounded retry pool (backoff+jitter), fail-fast |
| PrimeReact hex vs OKLCH tokens | Med | CSS-variable overrides, `tokens.css` |
| Hashing blocks event loop | Med | Executors/threads, async reads |

## Rollback Plan
Greenfield — nothing to revert. Abandon: delete change folder + Engram topic; `docker compose down -v`.

## Dependencies
Docker + compose; Python ≥ 3.11; Node ≥ 18; PostgreSQL 16.

## Success Criteria
- [ ] 4 tables; `checksum` UNIQUE; FK `logs_errores.correlation_id → sincronizaciones`
- [ ] Duplicate → original 200; corrupt payload → 422 + log row
- [ ] selectinload N+1-free; keyset works
- [ ] Compose: frontend only `frontend-net`, db only `db-net`, backend bridges
- [ ] Scripts + Jenkinsfile (checkout/lint/tests/build) pass; pytest + vitest ≥80%
- [ ] Frontend parity: debounce, VirtualScroller, focus trap, theme toggle

## Tasks
1. Schema+migrations · 2. Backend core · 3. Frontend scaffold+theme · 4. Screens · 5. DevOps · 6. Tests · 7. README
