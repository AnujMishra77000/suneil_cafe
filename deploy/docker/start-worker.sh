#!/usr/bin/env sh
set -eu

exec celery -A core worker \
  --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
  --concurrency="${CELERY_WORKER_CONCURRENCY:-4}"
