import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.http import HttpResponse


class LoginRateLimitMiddleware:
    """Simple IP-based limiter for Django admin login POST attempts."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_attempts = int(getattr(settings, "RATE_LIMIT_ADMIN_LOGIN_MAX_ATTEMPTS", 10))
        self.window_seconds = int(getattr(settings, "RATE_LIMIT_ADMIN_LOGIN_WINDOW_SECONDS", 60))

    @staticmethod
    def _client_ip(request):
        forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        return forwarded or request.META.get("REMOTE_ADDR", "unknown")

    def _increment(self, key):
        if cache.add(key, 1, timeout=self.window_seconds):
            return 1
        try:
            return cache.incr(key)
        except Exception:
            current = int(cache.get(key, 0)) + 1
            cache.set(key, current, timeout=self.window_seconds)
            return current

    def __call__(self, request):
        if request.method == "POST" and request.path.rstrip("/") == "/admin/login":
            ip = self._client_ip(request)
            cache_key = f"ratelimit:admin_login:{ip}"
            current = int(cache.get(cache_key, 0))
            if current >= self.max_attempts:
                return HttpResponse("Too many login attempts. Please try again shortly.", status=429)
            self._increment(cache_key)

        return self.get_response(request)


class _SlowQueryTimer:
    def __init__(self, threshold_ms, path):
        self.threshold_ms = threshold_ms
        self.path = path
        self.logger = logging.getLogger("core.slow_query")

    def __call__(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms >= self.threshold_ms:
                sql_preview = " ".join(str(sql).split())[:400]
                self.logger.warning(
                    "Slow query path=%s duration_ms=%.2f sql=%s",
                    self.path,
                    elapsed_ms,
                    sql_preview,
                )


class SlowQueryLoggingMiddleware:
    """Logs SQL statements slower than configured threshold."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        threshold_ms = int(getattr(settings, "SLOW_QUERY_MS", 500))
        if threshold_ms <= 0:
            return self.get_response(request)

        wrappers = []
        for connection in connections.all():
            cm = connection.execute_wrapper(_SlowQueryTimer(threshold_ms=threshold_ms, path=request.path))
            cm.__enter__()
            wrappers.append(cm)

        try:
            return self.get_response(request)
        finally:
            for cm in reversed(wrappers):
                cm.__exit__(None, None, None)
