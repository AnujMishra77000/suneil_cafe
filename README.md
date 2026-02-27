# Thathwamasi Ecommerce (Django)

Backend + frontend ecommerce system for **Bakery** and **Snacks** with:
- section/category/product browsing
- search
- cart
- billing
- checkout (name, mobile, address)
- order + bill generation (USER and ADMIN)

## Tech Stack
- Python + Django + Django REST Framework
- PostgreSQL (via `DATABASE_URL`)
- HTML/CSS/JS frontend templates served by Django

## Project Structure
- `products/` - storefront pages, product APIs
- `cart/` - cart APIs (add/view/update/remove/place)
- `orders/` - order + bill models/services/admin
- `users/` - customer model
- `core/` - Django settings/urls

## Setup
1. Create and activate virtual env (if not already active).
2. Install dependencies.
3. Configure `.env` in project root.
4. Run migrations.
5. Run server.

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
../Venv/bin/python manage.py migrate
../Venv/bin/python manage.py runserver 0.0.0.0:8000
```

## Required Environment Variables
Set in `/Users/anujmishra/Desktop/Thathwamasi/e_com/core/.env`

- `DATABASE_URL` (Postgres connection)
- `DJANGO_SECRET_KEY`
- `DEBUG` (`True`/`False`)
- `ALLOWED_HOSTS` (comma-separated)
- Optional:
  - `CSRF_TRUSTED_ORIGINS`
  - `CORS_ALLOWED_ORIGINS`
  - `CACHE_TIMEOUT`
  - Twilio vars if notifications are used

## Local + Mobile Access
If server runs with `0.0.0.0:8000`, open from mobile (same Wi-Fi):

- `http://<YOUR_LAN_IP>:8000/`
- Example: `http://192.168.0.112:8000/`

Do **not** use `python -m http.server` for this app.  
That only serves static files and does not run Django routes/templates.

## Main Frontend Routes
- Home: `/`
- Bakery: `/bakery/`
- Snacks: `/snacks/`
- Billing: `/billing/`
- Checkout: `/checkout/`

## API Endpoints
### Products
- `GET /api/products/sections/`
- `GET /api/products/category-cards/?section=snacks`
- `GET /api/products/sections/<section_id>/categories/`
- `GET /api/products/categories/<category_id>/products/`
- `GET /api/products/search/?q=<text>`
- `GET /api/products/<product_id>/related/`

### Cart
- `POST /api/cart/add/`
- `GET /api/cart/view/?phone=<mobile>`
- `POST /api/cart/item/update/`
- `POST /api/cart/item/remove/`
- `POST /api/cart/place/`

## Checkout Flow
1. User browses section/category products.
2. Adds items to cart (cart badge updates live).
3. Opens billing page and adjusts quantities.
4. Clicks **Proceed to Checkout**.
5. Enters name, mobile, whatsapp, address.
6. Places order.
7. System:
   - creates order + order items
   - deducts stock
   - creates USER and ADMIN bills
   - stores delivery info for admin visibility

## Admin
Open `/admin/` and manage:
- Sections, Categories, Products
- Customers (with address)
- Orders, OrderItems, Bills

## Performance Notes
Optimizations implemented:
- cached read endpoints
- gzip middleware
- lazy-loading images
- indexed customer phone lookups
- duplicate-customer/cart merge handling

## Troubleshooting
### 1. Home shows directory listing
You are using `http.server`. Run Django server instead.

### 2. `Unexpected token '<'`
Backend returned HTML error. Check API response in browser network tab and Django logs.

### 3. `get() returned more than one Customer`
Duplicate phone records. Resolver now handles this automatically.

### 4. `CombinedExpression` stock error
Fixed by using queryset update for stock deduction.

## Useful Commands
```bash
../Venv/bin/python manage.py check
../Venv/bin/python manage.py showmigrations
../Venv/bin/python manage.py migrate
```

## Load And Stress Testing (1k-2k concurrent users)

This project now includes:
- `scripts/locustfile.py` (realistic customer traffic model)
- `scripts/run_locust_load.sh` (headless runner + HTML/CSV reports)

### Install Locust
```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
/Users/anujmishra/Desktop/Thathwamasi/e_com/Venv/bin/pip install locust
```

### Quick Run (single machine)
```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
export LOAD_TEST_PINCODE=560001
./scripts/run_locust_load.sh https://YOUR-LIVE-DOMAIN 1200 100 20m false
```

Arguments for `run_locust_load.sh`:
1. `BASE_URL`
2. `USERS`
3. `SPAWN_RATE`
4. `RUN_TIME`
5. `USE_SHAPE` (`true` enables staged ramp profile)

### Staged Ramp To 2k Users
```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
export LOAD_TEST_PINCODE=560001
export LOCUST_STAGES_JSON='[{"duration":300,"users":300,"spawn_rate":60},{"duration":600,"users":700,"spawn_rate":80},{"duration":900,"users":1200,"spawn_rate":100},{"duration":1200,"users":2000,"spawn_rate":120}]'
./scripts/run_locust_load.sh https://YOUR-LIVE-DOMAIN 2000 120 25m true
```

### Distributed Stress Test (recommended for true 2k+ load)
Use one master + multiple workers (separate VMs/machines):

Master:
```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
locust -f scripts/locustfile.py --master --host https://YOUR-LIVE-DOMAIN
```

Worker (run on each worker machine):
```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
locust -f scripts/locustfile.py --worker --master-host <MASTER_PRIVATE_IP>
```

### What Locust Simulates
- browse home/categories/products/search
- add to cart and view cart
- place order using serviceable pincode

### Report Outputs
Each run writes:
- HTML report: `load_test_reports/<timestamp>/report.html`
- CSV stats: `load_test_reports/<timestamp>/locust_*.csv`

Use these thresholds for go/no-go:
- p95 API latency under ~800ms for read APIs
- order placement success path stable under target load
- HTTP 5xx near zero

### Automatic SLA Pass/Fail
`run_locust_load.sh` now runs SLA validation automatically using:
- `scripts/check_locust_sla.py`
- input: `locust_stats.csv`
- output: `sla_result.json`
- exit code: non-zero when SLA fails

SLA environment controls:
- `SLA_ENABLED=true|false`
- `SLA_MAX_ERROR_RATE=0.01`
- `SLA_MAX_P95_MS=800`
- `SLA_MAX_P99_MS=1500`
- `SLA_MAX_AVG_MS=500`
- `SLA_MIN_RPS=1`
- `SLA_MIN_REQUESTS=1000`
- `SLA_ENDPOINT_MAX_P95_MS=1200`
- `SLA_CRITICAL_ENDPOINTS=/api/products/category-cards/,/api/products/categories/[id]/products/,/api/cart/view/,/api/cart/add/,/api/cart/place/`
- `SLA_ALLOW_MISSING_CRITICAL=false`

Example strict run:
```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
export LOAD_TEST_PINCODE=560001
export SLA_MAX_ERROR_RATE=0.01
export SLA_MAX_P95_MS=850
export SLA_MAX_P99_MS=1600
./scripts/run_locust_load.sh https://YOUR-LIVE-DOMAIN 1200 100 20m true
```

### Preset Profiles (many more)
Use preset profiles with built-in traffic + SLA thresholds:
- `smoke`
- `load`
- `stress`
- `spike`
- `soak`
- `all` (runs all sequentially)

```bash
cd /Users/anujmishra/Desktop/Thathwamasi/e_com/core
export LOAD_TEST_PINCODE=560001
./scripts/run_load_profiles.sh https://YOUR-LIVE-DOMAIN smoke
./scripts/run_load_profiles.sh https://YOUR-LIVE-DOMAIN stress
```

### Scenario Tuning
Optional traffic-mix variables:
- `LOAD_BROWSING_WEIGHT` (default `7`)
- `LOAD_BUYER_WEIGHT` (default `3`)
- `LOAD_MIN_WAIT_SECONDS` (default `0.4`)
- `LOAD_MAX_WAIT_SECONDS` (default `2.0`)
- `LOAD_POST_ORDER_HISTORY_PROB` (default `0.5`)
- `LOAD_POST_ORDER_NOTIFICATION_PROB` (default `0.5`)

## Production Deploy (Gunicorn + Nginx)

This repo includes deploy templates:
- Gunicorn config: `deploy/gunicorn.conf.py`
- systemd service: `deploy/systemd/thathwamasi-gunicorn.service`
- Nginx site: `deploy/nginx/thathwamasi.conf`
- Production env template: `deploy/env/.env.production.example`
- Ubuntu setup script: `scripts/setup_nginx_gunicorn_ubuntu.sh`

### 1. Server Prerequisites (Ubuntu)
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx redis-server
```

### 2. App Paths (example)
```bash
sudo mkdir -p /srv/thathwamasi
sudo chown -R $USER:$USER /srv/thathwamasi
# place your project at: /srv/thathwamasi/core
```

### 3. Python Environment + Dependencies
```bash
cd /srv/thathwamasi/core
python3 -m venv /srv/thathwamasi/venv
/srv/thathwamasi/venv/bin/pip install --upgrade pip
/srv/thathwamasi/venv/bin/pip install django djangorestframework django-cors-headers dj-database-url python-dotenv psycopg2-binary celery redis django-redis gunicorn
```

### 4. Environment Config
```bash
cp /srv/thathwamasi/core/deploy/env/.env.production.example /srv/thathwamasi/core/.env
# edit .env values (domain, DB URL, secret key, redis, twilio, etc.)
```

### 5. One-Command Setup
```bash
cd /srv/thathwamasi/core
sudo bash scripts/setup_nginx_gunicorn_ubuntu.sh your-domain.com www.your-domain.com
```

### 6. Verify
```bash
systemctl status thathwamasi-gunicorn --no-pager
systemctl status nginx --no-pager
curl -I http://127.0.0.1:8000/
```

### 7. TLS (recommended)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### Notes
- `DEBUG` must be `False` in production.
- Static files are served by Nginx from `staticfiles/`.
- Gunicorn reads tuning from env (`GUNICORN_*`) via `deploy/gunicorn.conf.py`.
- Security proxy settings are env-based in Django settings (`SECURE_SSL_REDIRECT`, HSTS, forwarded host).

## Production Deploy (Hostinger VPS: Docker + Nginx + PgBouncer)

This stack is included in the repo for containerized production deploy:
- App image: `Dockerfile`
- Compose stack: `docker-compose.hostinger.yml`
- Nginx (HTTP): `deploy/docker/nginx/default.conf`
- Nginx (HTTPS template): `deploy/docker/nginx/default.tls.conf.example`
- PgBouncer image + runtime config: `deploy/docker/pgbouncer/`
- Hostinger env template: `deploy/env/hostinger.env.example`

### Architecture
- `nginx` -> reverse proxy + static/media
- `web` -> Django + Gunicorn
- `worker` -> Celery worker
- `redis` -> cache + broker
- `pgbouncer` -> connection pooling for local PostgreSQL

### 1. Hostinger VPS Prerequisites
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Compose plugin
docker compose version
```

### 2. Copy Project + Prepare Env
```bash
cd /opt
sudo mkdir -p thathwamasi
sudo chown -R $USER:$USER /opt/thathwamasi
# copy your project into /opt/thathwamasi/core

cd /opt/thathwamasi/core
cp deploy/env/hostinger.env.example deploy/env/hostinger.env
```

Edit `deploy/env/hostinger.env` carefully:
- Use strong `DJANGO_SECRET_KEY`
- Keep Django DB target as `pgbouncer:6432`
- Set local PostgreSQL vars (`POSTGRES_*`) and keep PgBouncer host as `postgres`
- Set `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `CORS_ALLOWED_ORIGINS`

### 3. Start Production Stack
```bash
docker compose -f docker-compose.hostinger.yml up -d --build
```

### 4. Verify Services
```bash
docker compose -f docker-compose.hostinger.yml ps
docker compose -f docker-compose.hostinger.yml logs -f web
docker compose -f docker-compose.hostinger.yml logs -f nginx
curl -I http://127.0.0.1/
```

### 5. HTTPS (Let's Encrypt)
1. Ensure DNS A record points to VPS.
2. Issue cert:
```bash
docker compose -f docker-compose.hostinger.yml --profile ops run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  -d your-domain.com -d www.your-domain.com \
  --email you@example.com --agree-tos --no-eff-email
```
3. Enable TLS config:
```bash
cp deploy/docker/nginx/default.tls.conf.example deploy/docker/nginx/default.conf
# replace domain values in default.conf
```
4. Reload nginx container:
```bash
docker compose -f docker-compose.hostinger.yml up -d nginx
```
5. After HTTPS is live, set in `deploy/env/hostinger.env`:
- `SECURE_SSL_REDIRECT=true`

### 6. Useful Operations
```bash
# restart one service
docker compose -f docker-compose.hostinger.yml restart web

# scale web replicas
docker compose -f docker-compose.hostinger.yml up -d --scale web=3

# run django shell
docker compose -f docker-compose.hostinger.yml exec web python manage.py shell

# create admin
docker compose -f docker-compose.hostinger.yml exec web python manage.py createsuperuser
```

### Production Notes
- Keep `DB_CONN_MAX_AGE=0` when using transaction-pooled PgBouncer.
- Keep `DEBUG=False` in production.
- Do not commit `deploy/env/hostinger.env`.
- Use Hostinger firewall/security groups to allow only `80/443`.
- For heavy traffic, increase `GUNICORN_WORKERS`, tune Redis memory, and use external observability.

### 7. Migrate Data from Existing PostgreSQL (one-time)
If your current data is in another PostgreSQL provider and you want to move fully to VPS Postgres:

1. Export from source PostgreSQL (run on your local machine):
```bash
pg_dump "postgresql://SOURCE_USER:SOURCE_PASS@SOURCE_HOST:5432/SOURCE_DB?sslmode=require" \
  --format=custom --no-owner --no-privileges \
  -f thathwamasi_source.dump
```

2. Copy dump to VPS:
```bash
scp thathwamasi_source.dump user@your-vps-ip:/opt/thathwamasi/core/
```

3. Restore into Docker Postgres (run on VPS):
```bash
cd /opt/thathwamasi/core
docker compose -f docker-compose.hostinger.yml up -d postgres
container_id=$(docker compose -f docker-compose.hostinger.yml ps -q postgres)
docker cp thathwamasi_source.dump "$container_id":/tmp/thathwamasi_source.dump
docker compose -f docker-compose.hostinger.yml exec -T postgres \
  sh -lc 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /tmp/thathwamasi_source.dump'
```
4. Start full stack:
```bash
docker compose -f docker-compose.hostinger.yml up -d --build
```

### 8. Optional Hardening for Production
- Add daily DB backup cron using `pg_dump` from the `postgres` container.
- Keep only ports `80/443` open publicly.
- Restrict SSH by IP and disable password login.
- Enable fail2ban + UFW.
- Add error monitoring (Sentry) and uptime checks.
