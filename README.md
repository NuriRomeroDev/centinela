# Centinela — Control & Auditoría

Plataforma fullstack de monitoreo de sincronizaciones y errores de ingestión para reconciliación bancaria. Backend FastAPI (async) con idempotencia por SHA-256 (replay-safe por `correlation_id`) y frontend React con dashboard de KPIs, logs virtualizados con búsqueda debounced, y explorador de sincronizaciones con historial de remediación.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.0 async · asyncpg · Alembic · Pydantic v2 |
| Frontend | React 18 · TypeScript · PrimeReact · TanStack Query · Vite |
| Base de datos | PostgreSQL 16 |
| DevOps | Docker Compose · Nginx · Jenkins |

## Requisitos

- Docker Engine + Docker Compose v2
- `bash` (Linux/macOS; Windows: WSL2 o Git Bash)

## Puesta en marcha

```bash
cp .env.example .env
./scripts/up.sh
```

`up.sh` construye, levanta el stack, ejecuta las migraciones y muestra las URLs:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Documentación OpenAPI: http://localhost:8000/docs

Con datos de demostración:

```bash
SEED=1 ./scripts/up.sh
```

## Scripts

| Script | Acción |
|---|---|
| `./scripts/up.sh` | Build + up + migraciones (+ seed con `SEED=1`) |
| `./scripts/clean.sh` | `docker compose down -v` (elimina el volumen `pgdata`) |
| `./scripts/test.sh` | Suites backend + frontend con cobertura ≥80 % |

## Testing

```bash
./scripts/test.sh
```

- **Backend**: `pytest --cov --cov-fail-under=80` — 136 tests, cobertura ~95 % (integración con testcontainers PostgreSQL).
- **Frontend**: `vitest run --coverage` — 71 tests, umbrales 80 %.

## API

Base: `/api/v1` — errores en formato `{error: {codigo, mensaje, correlation_id}}`.

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/v1/ingest` | POST | Ingesta raw body + headers (`X-File-Name`, `X-Tipo-Archivo`, `X-Checksum-SHA256`, `X-Correlation-Id?`). 201 / 200 replay / 422 / 503 |
| `/api/v1/dashboard/metrics` | GET | KPIs de la operación |
| `/api/v1/throughput?days=7` | GET | Throughput diario |
| `/api/v1/status-distribution` | GET | Distribución de estados |
| `/api/v1/logs` | GET | Paginación keyset (`cursor`) + offset + búsqueda |
| `/api/v1/logs/{id}` | GET | Detalle con stack trace |
| `/api/v1/syncs?include_files=true` | GET | Sincronizaciones con archivos |
| `/api/v1/remediations` | GET / POST | Historial y registro de remediaciones |
| `/api/v1/syncs/{id}/remediate` | POST | `{accion}` ∈ `RETRY_JOB`, `FORCE_SKIP_VALIDATION` |
| `/health` | GET | Liveness para healthchecks |

## Estructura

```
centinela/
├── docker-compose.yml     # db/backend/frontend, redes aisladas, volumen pgdata
├── Jenkinsfile            # checkout → lint → unit tests (≥80%) → docker build
├── scripts/               # up.sh, clean.sh, test.sh
├── .env.example
├── backend/               # FastAPI app/, migrations/, tests/, Dockerfile
└── frontend/              # React src/, Dockerfile + nginx.conf, vite.config.ts
```
