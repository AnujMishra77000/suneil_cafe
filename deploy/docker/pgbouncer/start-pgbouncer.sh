#!/usr/bin/env sh
set -eu

: "${PGBOUNCER_DB_HOST:?PGBOUNCER_DB_HOST is required}"
: "${PGBOUNCER_DB_NAME:?PGBOUNCER_DB_NAME is required}"
: "${PGBOUNCER_DB_USER:?PGBOUNCER_DB_USER is required}"
: "${PGBOUNCER_DB_PASSWORD:?PGBOUNCER_DB_PASSWORD is required}"

PGBOUNCER_DB_PORT="${PGBOUNCER_DB_PORT:-5432}"
PGBOUNCER_POOL_MODE="${PGBOUNCER_POOL_MODE:-transaction}"
PGBOUNCER_MAX_CLIENT_CONN="${PGBOUNCER_MAX_CLIENT_CONN:-1000}"
PGBOUNCER_DEFAULT_POOL_SIZE="${PGBOUNCER_DEFAULT_POOL_SIZE:-80}"
PGBOUNCER_RESERVE_POOL_SIZE="${PGBOUNCER_RESERVE_POOL_SIZE:-25}"
PGBOUNCER_SERVER_TLS_SSLMODE="${PGBOUNCER_SERVER_TLS_SSLMODE:-disable}"

cat > /etc/pgbouncer/userlist.txt <<USERLIST
"${PGBOUNCER_DB_USER}" "${PGBOUNCER_DB_PASSWORD}"
USERLIST

cat > /etc/pgbouncer/pgbouncer.ini <<CONFIG
[databases]
app = host=${PGBOUNCER_DB_HOST} port=${PGBOUNCER_DB_PORT} dbname=${PGBOUNCER_DB_NAME} user=${PGBOUNCER_DB_USER} password=${PGBOUNCER_DB_PASSWORD}

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = plain
auth_file = /etc/pgbouncer/userlist.txt
admin_users = ${PGBOUNCER_DB_USER}
stats_users = ${PGBOUNCER_DB_USER}
pool_mode = ${PGBOUNCER_POOL_MODE}
max_client_conn = ${PGBOUNCER_MAX_CLIENT_CONN}
default_pool_size = ${PGBOUNCER_DEFAULT_POOL_SIZE}
reserve_pool_size = ${PGBOUNCER_RESERVE_POOL_SIZE}
reserve_pool_timeout = 5
server_reset_query = DISCARD ALL
ignore_startup_parameters = extra_float_digits,options
server_tls_sslmode = ${PGBOUNCER_SERVER_TLS_SSLMODE}
client_tls_sslmode = disable
log_connections = 1
log_disconnections = 1
CONFIG

exec pgbouncer /etc/pgbouncer/pgbouncer.ini
