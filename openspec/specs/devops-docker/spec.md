# DevOps Docker Specification

## Purpose

Dockerized delivery with network isolation: docker-compose (db/backend/frontend), lifecycle scripts, and an env template. The frontend never reaches the DB network by construction.

## Requirements

### Requirement 1: Network isolation

docker-compose.yml MUST define at least two isolated networks: `frontend-net` and `db-net`. Service attachment MUST be: db -> db-net ONLY; frontend -> frontend-net ONLY; backend -> BOTH frontend-net and db-net (bridge). The frontend container MUST have no route to the db network and the db container MUST have no route to the frontend network.

#### Scenario: Isolation by construction

- GIVEN the compose topology
- WHEN inspecting container networks
- THEN frontend is attached only to frontend-net, db only to db-net, backend bridges both
- AND a packet from frontend to the db container is unreachable

### Requirement 2: Compose services

Services MUST be: `db` (postgres:16-alpine, pg_isready healthcheck, named volume, env from .env); `backend` (FastAPI + uvicorn image, depends_on db with service_healthy condition, env: POSTGRES_*, DATABASE_URL, CORS_ORIGINS, retry params); `frontend` (built React served by nginx or Vite dev, published port, and MUST NOT receive DATABASE_URL or any DB env). Backend and frontend ports MUST be configurable via .env.

#### Scenario: Healthy dependency ordering

- GIVEN `docker compose up -d`
- WHEN the backend starts
- THEN it waits until the db healthcheck passes before serving

### Requirement 3: Lifecycle scripts

`scripts/up.sh` MUST build images, start services detached, wait for db healthy, run migrations (alembic upgrade head), and report readiness URLs. `scripts/clean.sh` MUST run `docker compose down -v` (removes volumes). Both MUST be rerunnable, exit non-zero with a clear message on failure, and be executable.

#### Scenario: Clean teardown

- GIVEN a running compose stack with volumes
- WHEN scripts/clean.sh runs
- THEN containers stop and named volumes are removed

#### Scenario: Repeat up

- GIVEN an already-up stack
- WHEN scripts/up.sh runs again
- THEN compose reports no errors and the stack stays healthy

### Requirement 4: Test script

`scripts/test.sh` MUST run backend tests (pytest --cov --cov-fail-under=80) and frontend tests (npm test / vitest run --coverage), exiting non-zero if either suite fails or coverage is below 80%.

#### Scenario: Coverage gate

- GIVEN a backend suite at 75% coverage
- WHEN scripts/test.sh runs
- THEN the script exits non-zero and reports the coverage failure

### Requirement 5: Environment template

Repo root MUST include `.env.example` documenting: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DATABASE_URL, BACKEND_PORT, FRONTEND_PORT, CORS_ORIGINS, and DB retry params (initial backoff, max attempts, jitter). All values MUST be placeholders. `.gitignore` MUST exclude .env and local artifacts.

#### Scenario: Environment parity

- GIVEN a developer copies .env.example to .env
- WHEN `docker compose config` validates
- THEN the stack resolves all required env vars without warnings

### Requirement 6: CORS

The backend MUST allow CORS from the frontend origin (CORS_ORIGINS env, default http://localhost:{FRONTEND_PORT}).

#### Scenario: Cross-origin call

- GIVEN the SPA at http://localhost:5173 and the API at http://localhost:8000
- WHEN the SPA calls /api/v1/dashboard/metrics
- THEN preflight and response succeed with CORS headers for the configured origin

## Acceptance Criteria

- `docker compose up -d` brings up a healthy stack (db healthy -> backend ready -> frontend serving)
- Network isolation verified: frontend cannot reach db
- up.sh runs migrations; clean.sh removes volumes; both rerunnable
- test.sh gates on 80% coverage and exits non-zero on failure
- .env.example complete; CORS works for the frontend origin
