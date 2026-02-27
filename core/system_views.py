from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings


class ArchitectureStatusAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
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
