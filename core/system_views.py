from django.conf import settings
from django.utils.crypto import constant_time_compare
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class ArchitectureStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def _is_authorized(self, request):
        if bool(getattr(settings, "DEBUG", False)):
            return True

        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_staff:
            return True

        expected = (getattr(settings, "SYSTEM_ARCH_DEBUG_TOKEN", "") or "").strip()
        if not expected:
            return False

        provided = (
            request.headers.get("X-System-Token")
            or request.GET.get("token")
            or ""
        ).strip()
        if not provided:
            return False

        return constant_time_compare(provided, expected)

    def get(self, request):
        if not self._is_authorized(request):
            return Response({"detail": "Forbidden"}, status=403)

        cache_conf = (getattr(settings, "CACHES", {}) or {}).get("default", {})
        cache_backend = cache_conf.get("BACKEND", "")
        return Response(
            {
                "layered_architecture_enabled": bool(
                    getattr(settings, "USE_LAYERED_ARCHITECTURE", False)
                ),
                "mode": "layered"
                if getattr(settings, "USE_LAYERED_ARCHITECTURE", False)
                else "legacy",
                "debug": bool(getattr(settings, "DEBUG", False)),
                "cache_backend": cache_backend,
                "redis_configured": "django_redis" in str(cache_backend),
            }
        )
