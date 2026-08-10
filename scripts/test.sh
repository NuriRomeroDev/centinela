#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_RC=0
FRONTEND_RC=0

if [ -x backend/.venv/bin/pytest ]; then
    (cd backend && .venv/bin/pytest --cov --cov-fail-under=80) || BACKEND_RC=$?
elif command -v pytest >/dev/null 2>&1; then
    (cd backend && pytest --cov --cov-fail-under=80) || BACKEND_RC=$?
else
    echo "ERROR: pytest not found (backend/.venv/bin/pytest or PATH)" >&2
    BACKEND_RC=2
fi

(cd frontend && npm run test:coverage) || FRONTEND_RC=$?

echo
echo "== summary =="
if [ "$BACKEND_RC" -eq 0 ]; then
    echo "backend: PASS"
else
    echo "backend: FAIL (exit ${BACKEND_RC})"
fi
if [ "$FRONTEND_RC" -eq 0 ]; then
    echo "frontend: PASS"
else
    echo "frontend: FAIL (exit ${FRONTEND_RC})"
fi

if [ "$BACKEND_RC" -ne 0 ] || [ "$FRONTEND_RC" -ne 0 ]; then
    exit 1
fi
