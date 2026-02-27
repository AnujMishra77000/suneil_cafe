# Production 2K Runbook (Hostinger Docker)

## 1) Prelaunch config gate

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
./scripts/prelaunch_hostinger_check.sh
```

Fix any `FAIL` before moving ahead.

## 2) Install dependencies in app image environment

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
/Users/anujmishra/Desktop/Thathwamasi/e_com/Venv/bin/pip install -r requirements.txt
```

## 3) Backup database (mandatory)

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
ts=$(date +%F_%H%M%S)
mkdir -p deploy/backups
docker compose -f docker-compose.hostinger.yml exec -T postgres   sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"'   > "deploy/backups/db_${ts}.sql"
```

## 4) Apply migrations as release step

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
docker compose -f docker-compose.hostinger.yml run --rm web python manage.py migrate --noinput
docker compose -f docker-compose.hostinger.yml run --rm web python manage.py check --deploy
```

## 5) Deploy services

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
docker compose -f docker-compose.hostinger.yml up -d --build postgres pgbouncer redis
docker compose -f docker-compose.hostinger.yml up -d --build web worker nginx
```

## 6) Smoke tests (must pass)

Set these first:

```bash
BASE_URL="https://your-domain.com"
ARCH_TOKEN="<SYSTEM_ARCH_DEBUG_TOKEN value>"
```

Public app checks:

```bash
curl -fsS "$BASE_URL/api/products/sections/" >/dev/null
curl -fsS "$BASE_URL/api/orders/serviceable-pincodes/" >/dev/null
```

Security checks:

```bash
# architecture endpoint must be blocked without auth/token
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/system/architecture/")
echo "architecture_no_token=$code"  # expect 403 in prod

# with token should work
curl -fsS -H "X-System-Token: $ARCH_TOKEN" "$BASE_URL/api/system/architecture/" >/dev/null
```

Idempotency check (same key must not create duplicate orders):

```bash
IDEMP="$(python3 - <<'PY'
import uuid; print(uuid.uuid4())
PY)"
PHONE="9000012345"
PRODUCT_ID="$(curl -fsS "$BASE_URL/api/products/sections/1/products/" | python3 - <<'PY'
import json,sys
rows=json.load(sys.stdin)
print(rows[0]["id"] if rows else 1)
PY)"

ADD_PAYLOAD=$(cat <<JSON
{"phone":"$PHONE","product_id":$PRODUCT_ID,"quantity":1}
JSON
)

CHECKOUT_PAYLOAD=$(cat <<JSON
{"phone":"$PHONE","customer_name":"Smoke User","whatsapp_no":"$PHONE","address":"Test addr, 560001","pincode":"560001","cart_phone":"$PHONE","idempotency_key":"$IDEMP"}
JSON
)

curl -fsS -X POST "$BASE_URL/api/cart/add/" -H 'Content-Type: application/json' -d "$ADD_PAYLOAD" >/dev/null

r1=$(curl -sS -X POST "$BASE_URL/api/cart/place/" -H 'Content-Type: application/json' -d "$CHECKOUT_PAYLOAD")
r2=$(curl -sS -X POST "$BASE_URL/api/cart/place/" -H 'Content-Type: application/json' -d "$CHECKOUT_PAYLOAD")
echo "$r1"
echo "$r2"
```

## 7) 2k concurrency load test plan

### 7.1 Warm-up (smoke)

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
export LOAD_TEST_PINCODE=560001
./scripts/run_load_profiles.sh "$BASE_URL" smoke
```

### 7.2 Load profile

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
export LOAD_TEST_PINCODE=560001
./scripts/run_load_profiles.sh "$BASE_URL" load
```

### 7.3 2k stress profile

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
export LOAD_TEST_PINCODE=560001
./scripts/run_load_profiles.sh "$BASE_URL" stress
```

Reports are written under:

- `load_test_reports/<timestamp>/report.html`
- `load_test_reports/<timestamp>/sla_result.json`

## 8) Go/No-Go criteria

- Error rate <= 1-3% (based on chosen profile/SLA)
- p95 and p99 within your configured SLA thresholds
- Checkout success path stable under stress
- No sustained DB connection exhaustion
- No sustained Redis failures
- Sentry shows no critical unhandled exceptions during run
