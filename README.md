# Centinela — Control & Auditoría

Plataforma fullstack de monitoreo de sincronizaciones y errores de ingestión para reconciliación bancaria y control de idempotencia. El backend ingiere payloads crudos con idempotencia por SHA-256 (replay-safe por `correlation_id`) y el frontend replica la plantilla de referencia: dashboard con KPIs, gráfica de throughput, distribución de estados, errores recientes, logs virtualizados con búsqueda debounced de 300 ms, explorador de sincronizaciones con archivos expandibles e historial de remediación con modal de stack trace.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI (async) · SQLAlchemy 2.0 async · asyncpg · Alembic · Pydantic v2 |
| Frontend | React 18 · TypeScript strict · PrimeReact 10.9.8 (pin estable) · TanStack Query v5 · Vite |
| Base de datos | PostgreSQL 16 |
| DevOps | Docker Compose (redes aisladas) · Nginx · Jenkins declarativo |

## Arquitectura

```
┌──────────────┐  /api/v1/*   ┌────────────────────────────┐
│  SPA React   │─────────────▶│  Backend (FastAPI async)   │
│  Nginx:80    │  (proxy /api)│  uvicorn · SQLAlchemy      │
└──────────────┘              └─────────────┬──────────────┘
   red: frontend-net         red: frontend-net + db-net (puente)
                                            │ asyncpg (pool con retry acotado)
                                  ┌─────────▼─────────┐
                                  │ PostgreSQL 16     │
                                  │ 4 tablas, enums,  │
                                  │ checksum único    │
                                  └───────────────────┘
                                     red: db-net
```

Aislamiento por construcción: el contenedor `frontend` está adjunto **solo** a `frontend-net`, `db` **solo** a `db-net`, y `backend` puentea ambas. El frontend no recibe `DATABASE_URL` ni ninguna variable de base de datos y no tiene ruta de red hacia PostgreSQL.

## Prerequisitos

- Docker Engine + Docker Compose v2 (Docker Desktop en macOS/Windows)
- `bash` (Linux/macOS; en Windows usar WSL2 o Git Bash)
- Puertos libres: `8000` (backend) y `5173` (frontend) — configurables en `.env`

## Puesta en marcha

```bash
cp .env.example .env
./scripts/up.sh
```

`up.sh` construye las imágenes, levanta el stack, espera a que la base quede healthy, ejecuta las migraciones (`alembic upgrade head`) y muestra las URLs:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Documentación OpenAPI: http://localhost:8000/docs

Para cargar además el seed idempotente (datos de demostración que replican la plantilla):

```bash
SEED=1 ./scripts/up.sh
```

El script es rerunnable: si el stack ya está arriba, no falla y mantiene el estado.

## Scripts

| Script | Acción |
|---|---|
| `./scripts/up.sh` | build → up -d → espera db healthy → migraciones → (SEED=1 opcional) → URLs. Salida non-zero ante error |
| `./scripts/clean.sh` | `docker compose down -v` — detiene contenedores y elimina el volumen `pgdata` (destructivo) |
| `./scripts/test.sh` | Suites backend + frontend con umbral de cobertura ≥80 %. Ejecuta ambas y sale non-zero si alguna falla |

## Testing

```bash
./scripts/test.sh
```

- **Backend**: `pytest --cov --cov-fail-under=80` — 136 tests (unitarios + integración con testcontainers PostgreSQL), cobertura 95.05 %.
- **Frontend**: `vitest run --coverage` — 71 tests, umbrales 80 % en lines/functions/branches/statements.

La suite de integración del backend requiere Docker (testcontainers levanta un PostgreSQL efímero).

### Notas sobre los tests de estrés

- **Caída de base de datos (T2.10)**: con la adquisición de conexión envuelta en retry acotado (backoff exponencial + jitter, `DB_RETRY_MAX_ATTEMPTS`), la API responde **503 fail-fast** (`ERR_POOL_EXHAUSTED` / `ERR_DB_TIMEOUT`) en tiempo acotado — sin cuelgues — y se auto-recupera cuando la base vuelve. El test asevera el tiempo de pared acotado.
- **Payloads corruptos concurrentes**: el test de ingestión aísla un payload corrupto (422 + fila de log ligada a `correlation_id`) de peticiones healthy concurrentes — la disponibilidad se preserva, los handlers son por-request.
- **N+1 / query-count**: los endpoints de dashboard, syncs y remediations se aseveran con contador de statements SQL (O(1) sobre 1,000 filas).

## API

Base: `/api/v1` — respuestas de error en formato `{error: {codigo, mensaje, correlation_id}}`.

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/v1/ingest` | POST | Ingesta raw body + headers `X-Correlation-Id?`, `X-File-Name`, `X-Tipo-Archivo`, `X-Checksum-SHA256`. 201 / 200 replay / 422 / 503 |
| `/api/v1/dashboard/metrics` | GET | KPIs: activas, completadas hoy, archivos rechazados, tasa de errores críticos |
| `/api/v1/throughput?days=7` | GET | Throughput diario (7 días por defecto, clamp 1–30, zero-fill) |
| `/api/v1/status-distribution` | GET | Distribución de estados con porcentaje |
| `/api/v1/logs/recent?limit=5` | GET | Logs recientes (sin `stack_trace`) |
| `/api/v1/logs` | GET | Paginación keyset (`cursor`) + offset (`page`/`page_size` ≤100) + búsqueda ILIKE |
| `/api/v1/logs/{id}` | GET | Detalle con `stack_trace`; 404 si no existe |
| `/api/v1/syncs?include_files=true` | GET | Sincronizaciones con archivos embebidos y `archivos_resumen` |
| `/api/v1/remediations` | GET | Historial de remediaciones (más reciente primero) |
| `/api/v1/remediations` | POST | Registrar remediación → 201 / 422 / 404 |
| `/api/v1/syncs/{id}/remediate` | POST | `{accion}` ∈ {RETRY_JOB, FORCE_SKIP_VALIDATION} → 200 / 422 / 404 |
| `/health` | GET | Liveness para healthchecks de Docker Compose |

## Estructura del proyecto

```
centinela/
├── docker-compose.yml        # db/backend/frontend, frontend-net + db-net, volumen pgdata
├── Jenkinsfile               # checkout → lint → unit tests (≥80%) → docker build
├── scripts/                  # up.sh, clean.sh, test.sh
├── .env.example              # plantilla de variables de entorno
├── backend/
│   ├── app/                  # api/, core/, db/, models/, schemas/, services/, main.py
│   ├── migrations/           # Alembic (single head 0001_initial)
│   ├── tests/                # unit/ + integration/ (testcontainers)
│   ├── pyproject.toml        # deps, black/flake8/pytest/coverage
│   └── Dockerfile            # python:3.12-slim, non-root
├── frontend/
│   ├── src/                  # app/, api/, types/, hooks/, components/, pages/, styles/
│   ├── Dockerfile            # multi-stage node:18-alpine build → nginx:alpine
│   ├── nginx.conf            # SPA fallback + proxy /api → backend:8000
│   └── vite.config.ts        # proxy dev /api → localhost:8000
└── openspec/                 # artefactos SDD (specs, change, config)
```

## Decisiones de diseño

- **Idempotencia**: SHA-256 incremental en chunks de 8 KB (hashing fuera del event loop vía `asyncio.to_thread`); detección de duplicados de doble capa (pre-check + catch de `IntegrityError`, TOCTOU-safe) → replay responde 200 con el payload original y registra `ERR_DUPLICATE_BATCH`.
- **Resiliencia**: retry a nivel de adquisición de conexión (`retry_acquire`, backoff exponencial + jitter acotado por env) — no a nivel de middleware HTTP, para no reintentar escrituras con resultado ambiguo. `pool_pre_ping` evita conexiones muertas tras reinicio de la base.
- **Redes aisladas**: dos redes bridge (`frontend-net`, `db-net`); el backend puentea ambas, el frontend nunca alcanza PostgreSQL por construcción y no recibe credenciales de base de datos.
- **CORS**: `CORS_ORIGINS` se define en `.env` (por defecto el origen del frontend, `http://localhost:5173`) — necesario para desarrollo local (SPA → API directo). En el stack dockerizado el frontend llama al backend vía proxy de nginx (`/api` → `backend:8000`), por lo que CORS no interviene.
- **Migraciones**: se ejecutan desde `scripts/up.sh` (`alembic upgrade head` dentro del contenedor backend), no como servicio de compose.

## Variables de entorno

`.env.example` documenta: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL` (para desarrollo local fuera de Docker; en compose se reescribe al host `db:5432`), `BACKEND_PORT`, `FRONTEND_PORT`, `CORS_ORIGINS` (JSON array) y los parámetros de pool (`DB_POOL_*`) y retry (`DB_RETRY_*`). Ningún secreto real se versiona — solo placeholders.

## Jenkins local

1. Levantar un Jenkins con Docker (con acceso al socket de Docker para la etapa de build):

```bash
docker run -p 8080:8080 -p 50000:50000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts
```

2. Crear un job **Pipeline** → *Pipeline script from SCM* → repositorio local de Centinela → script path `Jenkinsfile`.
3. El pipeline ejecuta 4 etapas: **Checkout → Linter & Static Analysis → Unit Testing → Docker Build**. El agente necesita Python 3.12, Node 18 y Docker (o usar agentes con imágenes que los incluyan); los tests de integración del backend usan testcontainers (requiere Docker en el agente).
4. Cualquier fallo de lint, test o cobertura <80 % detiene el build (fail-fast). No se publica ni despliega nada.
