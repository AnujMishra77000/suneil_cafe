#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${1:-http://127.0.0.1:8000}"
PROFILE="${2:-all}"

run_profile() {
  local name="$1"
  local users="$2"
  local spawn="$3"
  local duration="$4"
  local shape="$5"
  local max_error_rate="$6"
  local max_p95="$7"
  local max_p99="$8"
  local max_avg="$9"
  local min_rps="${10}"
  local min_requests="${11}"
  local endpoint_max_p95="${12}"
  local stage_json="${13:-}"

  echo
  echo "=============================="
  echo "Running profile: $name"
  echo "users=$users spawn=$spawn duration=$duration shape=$shape"
  echo "SLA: error<=$max_error_rate p95<=$max_p95 p99<=$max_p99 avg<=$max_avg min_rps>=$min_rps"
  echo "=============================="

  (
    export SLA_ENABLED=true
    export SLA_MAX_ERROR_RATE="$max_error_rate"
    export SLA_MAX_P95_MS="$max_p95"
    export SLA_MAX_P99_MS="$max_p99"
    export SLA_MAX_AVG_MS="$max_avg"
    export SLA_MIN_RPS="$min_rps"
    export SLA_MIN_REQUESTS="$min_requests"
    export SLA_ENDPOINT_MAX_P95_MS="$endpoint_max_p95"
    export SLA_CRITICAL_ENDPOINTS="${SLA_CRITICAL_ENDPOINTS:-/api/products/category-cards/,/api/products/categories/[id]/products/,/api/cart/view/,/api/cart/add/,/api/cart/place/}"
    export SLA_ALLOW_MISSING_CRITICAL="${SLA_ALLOW_MISSING_CRITICAL:-false}"

    if [[ -n "$stage_json" ]]; then
      export LOCUST_STAGES_JSON="$stage_json"
    fi

    "$ROOT_DIR/scripts/run_locust_load.sh" "$BASE_URL" "$users" "$spawn" "$duration" "$shape"
  )
}

case "$PROFILE" in
  smoke)
    run_profile "smoke" 120 30 8m false 0.01 700 1300 450 5 800 900
    ;;
  load)
    run_profile \
      "load" \
      1200 \
      100 \
      20m \
      true \
      0.015 \
      900 \
      1800 \
      600 \
      20 \
      5000 \
      1300 \
      '[{"duration":300,"users":300,"spawn_rate":60},{"duration":600,"users":700,"spawn_rate":80},{"duration":900,"users":1200,"spawn_rate":100}]'
    ;;
  stress)
    run_profile \
      "stress" \
      2000 \
      120 \
      25m \
      true \
      0.03 \
      1300 \
      2500 \
      900 \
      30 \
      9000 \
      1800 \
      '[{"duration":300,"users":400,"spawn_rate":80},{"duration":900,"users":1200,"spawn_rate":100},{"duration":1500,"users":2000,"spawn_rate":140}]'
    ;;
  spike)
    run_profile \
      "spike" \
      2000 \
      220 \
      14m \
      true \
      0.04 \
      1600 \
      3200 \
      1100 \
      25 \
      6000 \
      2200 \
      '[{"duration":120,"users":250,"spawn_rate":80},{"duration":240,"users":2000,"spawn_rate":300},{"duration":540,"users":500,"spawn_rate":180},{"duration":840,"users":1200,"spawn_rate":80}]'
    ;;
  soak)
    run_profile \
      "soak" \
      700 \
      60 \
      90m \
      true \
      0.015 \
      1000 \
      2000 \
      700 \
      15 \
      15000 \
      1500 \
      '[{"duration":600,"users":500,"spawn_rate":50},{"duration":1800,"users":700,"spawn_rate":40},{"duration":3600,"users":700,"spawn_rate":30},{"duration":5400,"users":700,"spawn_rate":20}]'
    ;;
  all)
    "$ROOT_DIR/scripts/run_load_profiles.sh" "$BASE_URL" smoke
    "$ROOT_DIR/scripts/run_load_profiles.sh" "$BASE_URL" load
    "$ROOT_DIR/scripts/run_load_profiles.sh" "$BASE_URL" stress
    "$ROOT_DIR/scripts/run_load_profiles.sh" "$BASE_URL" spike
    "$ROOT_DIR/scripts/run_load_profiles.sh" "$BASE_URL" soak
    ;;
  *)
    echo "Unknown profile: $PROFILE"
    echo "Use one of: smoke | load | stress | spike | soak | all"
    exit 1
    ;;
esac
