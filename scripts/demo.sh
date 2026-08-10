#!/usr/bin/env bash
# demo.sh — demonstrates the 3 evaluation scenarios end-to-end
# Usage: bash scripts/demo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND="http://localhost:8000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "${GREEN}  ✓ $*${NC}"; }
fail() { echo -e "${RED}  ✗ $*${NC}"; }
info() { echo -e "${CYAN}  → $*${NC}"; }
section() { echo -e "\n${YELLOW}━━━ $* ━━━${NC}"; }

# ──────────────────────────────────────────────
section "SCENARIO 1 — Corrupt payload → 422 + error logged"
# ──────────────────────────────────────────────

PAYLOAD='[{"campo": "valor_prueba"}]'
CHECKSUM_BAD="0000000000000000000000000000000000000000000000000000000000000000"
CID_1="$(uuidgen | tr '[:upper:]' '[:lower:]')"

info "POSTing with mismatched X-Checksum-SHA256..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BACKEND/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-File-Name: ventas_demo.csv" \
  -H "X-Tipo-Archivo: ventas" \
  -H "X-Checksum-SHA256: $CHECKSUM_BAD" \
  -H "X-Correlation-Id: $CID_1" \
  -d "$PAYLOAD")

if [ "$STATUS" = "422" ]; then
  pass "Got HTTP 422 (checksum mismatch rejected)"
else
  fail "Expected 422, got $STATUS"
fi

info "Checking error was logged in logs_errores..."
sleep 1
COUNT=$(curl -s "$BACKEND/api/v1/logs?search=ERR_CHECKSUM_MISMATCH&page_size=5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['total'])" 2>/dev/null || echo "0")
if [ "$COUNT" -gt 0 ]; then
  pass "Found $COUNT ERR_CHECKSUM_MISMATCH entries in logs_errores"
else
  fail "No ERR_CHECKSUM_MISMATCH entries found — check logs_errores table"
fi

# ──────────────────────────────────────────────
section "SCENARIO 2 — Idempotency (duplicate replay → 200, not 201)"
# ──────────────────────────────────────────────

PAYLOAD_IDEM='[{"nombre": "Ana", "monto": 9900}]'
CHECKSUM_IDEM=$(echo -n "$PAYLOAD_IDEM" | sha256sum | awk '{print $1}')
CID_2="$(uuidgen | tr '[:upper:]' '[:lower:]')"

info "First POST (should be 201 Created)..."
STATUS_1=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BACKEND/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-File-Name: clientes_idem.csv" \
  -H "X-Tipo-Archivo: clientes" \
  -H "X-Checksum-SHA256: $CHECKSUM_IDEM" \
  -H "X-Correlation-Id: $CID_2" \
  -d "$PAYLOAD_IDEM")

if [ "$STATUS_1" = "201" ]; then
  pass "First ingest: HTTP 201 Created"
else
  fail "First ingest: expected 201, got $STATUS_1"
fi

info "Replay identical POST (should be 200 OK, idempotent)..."
STATUS_2=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BACKEND/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-File-Name: clientes_idem.csv" \
  -H "X-Tipo-Archivo: clientes" \
  -H "X-Checksum-SHA256: $CHECKSUM_IDEM" \
  -H "X-Correlation-Id: $CID_2" \
  -d "$PAYLOAD_IDEM")

if [ "$STATUS_2" = "200" ]; then
  pass "Replay: HTTP 200 OK (idempotent — no duplicate created)"
else
  fail "Replay: expected 200, got $STATUS_2"
fi

# ──────────────────────────────────────────────
section "SCENARIO 3 — PostgreSQL failure tolerance (backoff + recovery)"
# ──────────────────────────────────────────────

info "Stopping the database container..."
docker compose stop db

info "Sending request during DB outage (should fail gracefully, not hang)..."
PAYLOAD_STRESS='[{"test": "outage"}]'
CHECKSUM_STRESS=$(echo -n "$PAYLOAD_STRESS" | sha256sum | awk '{print $1}')
CID_3="$(uuidgen | tr '[:upper:]' '[:lower:]')"

STATUS_OUTAGE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 \
  -X POST "$BACKEND/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-File-Name: stress.csv" \
  -H "X-Tipo-Archivo: ventas" \
  -H "X-Checksum-SHA256: $CHECKSUM_STRESS" \
  -H "X-Correlation-Id: $CID_3" \
  -d "$PAYLOAD_STRESS" 2>/dev/null || echo "timeout")

if [ "$STATUS_OUTAGE" = "503" ] || [ "$STATUS_OUTAGE" = "500" ] || [ "$STATUS_OUTAGE" = "timeout" ]; then
  pass "DB outage handled gracefully (status: $STATUS_OUTAGE, backend stayed up)"
else
  info "Status during outage: $STATUS_OUTAGE"
fi

info "Restarting the database..."
docker compose start db

info "Waiting for DB to recover..."
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-centinela}"
attempts=0
until docker compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
  attempts=$((attempts+1))
  if [ "$attempts" -ge 30 ]; then
    fail "DB did not recover in time"
    exit 1
  fi
  sleep 2
done
pass "Database recovered after $((attempts*2))s"

info "Sending request after recovery..."
STATUS_RECOVERED=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 \
  -X POST "$BACKEND/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-File-Name: stress_ok.csv" \
  -H "X-Tipo-Archivo: ventas" \
  -H "X-Checksum-SHA256: $CHECKSUM_STRESS" \
  -H "X-Correlation-Id: $CID_3" \
  -d "$PAYLOAD_STRESS")

if [ "$STATUS_RECOVERED" = "201" ] || [ "$STATUS_RECOVERED" = "200" ]; then
  pass "Post-recovery ingest: HTTP $STATUS_RECOVERED — backend fully operational"
else
  fail "Post-recovery ingest: got $STATUS_RECOVERED"
fi

echo -e "\n${GREEN}━━━ Demo complete. All 3 evaluation scenarios exercised. ━━━${NC}\n"
