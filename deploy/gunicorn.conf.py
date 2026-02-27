"""Gunicorn config tuned for production baseline traffic."""

import os


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")

# Baseline for medium VPS. Scale workers based on CPU and p95 latency:
# roughly (2 x CPU cores) + 1, while watching DB/Redis saturation.
workers = _env_int("GUNICORN_WORKERS", 5)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = _env_int("GUNICORN_THREADS", 2)

timeout = _env_int("GUNICORN_TIMEOUT", 60)
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _env_int("GUNICORN_KEEPALIVE", 5)

max_requests = _env_int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 100)
preload_app = os.getenv("GUNICORN_PRELOAD_APP", "true").lower() == "true"

loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
capture_output = True

# Avoid leaking server version details.
server_tokens = False
