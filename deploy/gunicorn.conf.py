"""Gunicorn config for Thathwamasi production deployment."""

from __future__ import annotations

import multiprocessing
import os


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


cpu_count = multiprocessing.cpu_count()
default_workers = max(3, cpu_count * 2 + 1)

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = _env_int("GUNICORN_WORKERS", default_workers)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = _env_int("GUNICORN_THREADS", 4)
timeout = _env_int("GUNICORN_TIMEOUT", 120)
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _env_int("GUNICORN_KEEPALIVE", 5)
max_requests = _env_int("GUNICORN_MAX_REQUESTS", 2000)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 200)

loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
capture_output = True

# Avoid leaking server version details.
server_tokens = False
