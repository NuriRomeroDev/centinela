#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is required but was not found in PATH" >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: docker daemon is not running" >&2
    exit 1
fi

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-centinela}"

docker compose build
docker compose up -d

echo "waiting for database to become healthy..."
attempts=0
max_attempts=60
until docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge "$max_attempts" ]; then
        echo "ERROR: database did not become healthy in time" >&2
        exit 1
    fi
    sleep 2
done

docker compose exec -T backend alembic upgrade head

if [ "${SEED:-0}" = "1" ]; then
    docker compose exec -T backend python -m app.db.seed
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
echo "Centinela is up:"
echo "  frontend: http://localhost:${FRONTEND_PORT}"
echo "  backend:  http://localhost:${BACKEND_PORT}"
echo "  api docs: http://localhost:${BACKEND_PORT}/docs"
