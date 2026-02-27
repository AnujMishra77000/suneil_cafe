#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/deploy/env/hostinger.env}"
COMPOSE_FILE="$ROOT_DIR/docker-compose.hostinger.yml"
SETTINGS_FILE="$ROOT_DIR/core/settings.py"
REQ_FILE="$ROOT_DIR/requirements.txt"
START_WEB_FILE="$ROOT_DIR/deploy/docker/start-web.sh"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE"
  exit 2
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: compose file not found: $COMPOSE_FILE"
  exit 2
fi

fails=0
warns=0

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1"; fails=$((fails + 1)); }
warn() { echo "WARN  $1"; warns=$((warns + 1)); }

get_env() {
  local key="$1"
  awk -F= -v k="$key" '$1==k{print substr($0, index($0, "=")+1)}' "$ENV_FILE" | tail -n1
}

contains_placeholder() {
  local value="$1"
  [[ "$value" == *"replace_with"* || "$value" == *"replace-with"* || "$value" == *"your-domain.com"* || "$value" == *"changeme"* ]]
}

DEBUG_VAL="$(get_env DEBUG)"
DATABASE_URL_VAL="$(get_env DATABASE_URL)"
REDIS_URL_VAL="$(get_env REDIS_URL)"
SECRET_VAL="$(get_env DJANGO_SECRET_KEY)"
ARCH_TOKEN_VAL="$(get_env SYSTEM_ARCH_DEBUG_TOKEN)"
SENTRY_DSN_VAL="$(get_env SENTRY_DSN)"

if [[ "$DEBUG_VAL" == "False" ]]; then
  pass "DEBUG=False in hostinger env"
else
  fail "DEBUG must be False in hostinger env"
fi

if [[ -n "$SECRET_VAL" ]] && ! contains_placeholder "$SECRET_VAL"; then
  pass "DJANGO_SECRET_KEY is set and not placeholder"
else
  fail "DJANGO_SECRET_KEY missing or placeholder"
fi

if [[ -n "$DATABASE_URL_VAL" ]] && [[ "$DATABASE_URL_VAL" == *"@pgbouncer:6432/app"* ]]; then
  pass "DATABASE_URL uses PgBouncer alias app"
else
  fail "DATABASE_URL should point to @pgbouncer:6432/app"
fi

if [[ -n "$REDIS_URL_VAL" ]]; then
  pass "REDIS_URL is set"
else
  fail "REDIS_URL is required for DEBUG=False"
fi

if [[ -n "$ARCH_TOKEN_VAL" ]] && ! contains_placeholder "$ARCH_TOKEN_VAL"; then
  pass "SYSTEM_ARCH_DEBUG_TOKEN is set and not placeholder"
else
  fail "SYSTEM_ARCH_DEBUG_TOKEN missing or placeholder"
fi

if [[ -n "$SENTRY_DSN_VAL" ]] && [[ "$SENTRY_DSN_VAL" == http* ]]; then
  pass "SENTRY_DSN is configured"
else
  warn "SENTRY_DSN not configured (recommended for production incident visibility)"
fi

if rg -n '/api/products/sections/' "$COMPOSE_FILE" >/dev/null 2>&1; then
  pass "Web healthcheck uses public endpoint"
else
  fail "Web healthcheck should use /api/products/sections/"
fi

if rg -n 'sentry-sdk\[django,celery\]' "$REQ_FILE" >/dev/null 2>&1; then
  pass "sentry-sdk dependency present"
else
  fail "sentry-sdk dependency missing in requirements.txt"
fi

if rg -n 'raise ImproperlyConfigured\("REDIS_URL must be set when DEBUG=False"\)' "$SETTINGS_FILE" >/dev/null 2>&1; then
  pass "settings enforces REDIS_URL in production"
else
  fail "settings does not enforce REDIS_URL in production"
fi

if rg -n 'RUN_MIGRATIONS_ON_BOOT' "$START_WEB_FILE" >/dev/null 2>&1; then
  pass "start-web does not force migrations every boot"
else
  fail "start-web should gate migrations/collectstatic behind env flags"
fi

echo
if [[ "$fails" -gt 0 ]]; then
  echo "Prelaunch check: FAIL ($fails failed, $warns warnings)"
  exit 1
fi

echo "Prelaunch check: PASS ($warns warnings)"
