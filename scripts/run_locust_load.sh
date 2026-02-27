#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${1:-http://127.0.0.1:8000}"
USERS="${2:-1200}"
SPAWN_RATE="${3:-100}"
RUN_TIME="${4:-20m}"
USE_SHAPE="${5:-false}"

SLA_ENABLED="${SLA_ENABLED:-true}"
SLA_MAX_ERROR_RATE="${SLA_MAX_ERROR_RATE:-0.01}"
SLA_MAX_P95_MS="${SLA_MAX_P95_MS:-800}"
SLA_MAX_P99_MS="${SLA_MAX_P99_MS:-1500}"
SLA_MAX_AVG_MS="${SLA_MAX_AVG_MS:-500}"
SLA_MIN_RPS="${SLA_MIN_RPS:-1}"
SLA_MIN_REQUESTS="${SLA_MIN_REQUESTS:-1000}"
SLA_ENDPOINT_MAX_P95_MS="${SLA_ENDPOINT_MAX_P95_MS:-1200}"
SLA_CRITICAL_ENDPOINTS="${SLA_CRITICAL_ENDPOINTS:-/api/products/category-cards/,/api/products/categories/[id]/products/,/api/cart/view/,/api/cart/add/,/api/cart/place/}"
SLA_ALLOW_MISSING_CRITICAL="${SLA_ALLOW_MISSING_CRITICAL:-false}"

if ! command -v locust >/dev/null 2>&1; then
  echo "locust is not installed."
  echo "Install with: /Users/anujmishra/Desktop/Thathwamasi/e_com/Venv/bin/pip install locust"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$ROOT_DIR/load_test_reports/$STAMP"
mkdir -p "$OUT_DIR"

if [[ "${LOAD_TEST_PINCODE:-}" == "" ]]; then
  echo "Warning: LOAD_TEST_PINCODE is not set."
  echo "Locust will try /api/orders/serviceable-pincodes/ for valid pincodes."
fi

export LOCUST_USE_SHAPE="$USE_SHAPE"

echo "Running Locust"
echo "  Host      : $BASE_URL"
echo "  Users     : $USERS"
echo "  SpawnRate : $SPAWN_RATE"
echo "  RunTime   : $RUN_TIME"
echo "  UseShape  : $USE_SHAPE"
echo "  Reports   : $OUT_DIR"

set +e
locust \
  -f "$ROOT_DIR/scripts/locustfile.py" \
  --host "$BASE_URL" \
  --headless \
  -u "$USERS" \
  -r "$SPAWN_RATE" \
  --run-time "$RUN_TIME" \
  --stop-timeout 30 \
  --only-summary \
  --exit-code-on-error 0 \
  --csv "$OUT_DIR/locust" \
  --html "$OUT_DIR/report.html"
LOCUST_EXIT_CODE=$?
set -e

if [[ "$LOCUST_EXIT_CODE" -ne 0 ]]; then
  echo
  echo "Locust run failed with exit code: $LOCUST_EXIT_CODE"
  echo "Report directory: $OUT_DIR"
  exit "$LOCUST_EXIT_CODE"
fi

SLA_ENABLED_NORMALIZED="$(echo "$SLA_ENABLED" | tr '[:upper:]' '[:lower:]')"
SLA_JSON_PATH="$OUT_DIR/sla_result.json"

if [[ "$SLA_ENABLED_NORMALIZED" == "1" || "$SLA_ENABLED_NORMALIZED" == "true" || "$SLA_ENABLED_NORMALIZED" == "yes" || "$SLA_ENABLED_NORMALIZED" == "on" ]]; then
  SLA_ARGS=(
    --stats-csv "$OUT_DIR/locust_stats.csv"
    --summary-out "$SLA_JSON_PATH"
    --max-error-rate "$SLA_MAX_ERROR_RATE"
    --max-p95-ms "$SLA_MAX_P95_MS"
    --max-p99-ms "$SLA_MAX_P99_MS"
    --max-avg-ms "$SLA_MAX_AVG_MS"
    --min-rps "$SLA_MIN_RPS"
    --min-requests "$SLA_MIN_REQUESTS"
    --critical-endpoints "$SLA_CRITICAL_ENDPOINTS"
    --endpoint-max-p95-ms "$SLA_ENDPOINT_MAX_P95_MS"
  )

  ALLOW_MISSING_NORMALIZED="$(echo "$SLA_ALLOW_MISSING_CRITICAL" | tr '[:upper:]' '[:lower:]')"
  if [[ "$ALLOW_MISSING_NORMALIZED" == "1" || "$ALLOW_MISSING_NORMALIZED" == "true" || "$ALLOW_MISSING_NORMALIZED" == "yes" || "$ALLOW_MISSING_NORMALIZED" == "on" ]]; then
    SLA_ARGS+=(--allow-missing-critical)
  fi

  echo
  echo "Running SLA pass/fail checks"
  set +e
  python3 "$ROOT_DIR/scripts/check_locust_sla.py" "${SLA_ARGS[@]}"
  SLA_EXIT_CODE=$?
  set -e

  if [[ "$SLA_EXIT_CODE" -ne 0 ]]; then
    echo
    echo "SLA check FAILED."
    echo "Open HTML report: $OUT_DIR/report.html"
    echo "Open SLA JSON  : $SLA_JSON_PATH"
    exit "$SLA_EXIT_CODE"
  fi

  echo "SLA check PASSED."
else
  echo
  echo "SLA checks are disabled (SLA_ENABLED=$SLA_ENABLED)."
fi

echo
echo "Load test complete."
echo "Open report: $OUT_DIR/report.html"
if [[ -f "$SLA_JSON_PATH" ]]; then
  echo "Open SLA JSON: $SLA_JSON_PATH"
fi
