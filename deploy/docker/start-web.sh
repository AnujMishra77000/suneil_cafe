#!/usr/bin/env sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn core.wsgi:application -c deploy/gunicorn.conf.py
