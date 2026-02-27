#!/usr/bin/env sh
set -eu

# Run DB/schema/static steps in release pipeline, not at every app boot.
if [ "${RUN_MIGRATIONS_ON_BOOT:-false}" = "true" ]; then
  python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC_ON_BOOT:-false}" = "true" ]; then
  python manage.py collectstatic --noinput
fi

exec gunicorn core.wsgi:application -c deploy/gunicorn.conf.py
