from django.core.cache import cache
from django.utils import timezone

CATALOG_VERSION_KEY = "products:catalog:version"


def _new_version_value() -> int:
    return int(timezone.now().timestamp())


def get_catalog_cache_version() -> int:
    version = cache.get(CATALOG_VERSION_KEY)
    if version is None:
        version = _new_version_value()
        cache.set(CATALOG_VERSION_KEY, version, None)
    return int(version)


def catalog_cache_key(namespace: str, *parts) -> str:
    version = get_catalog_cache_version()
    normalized_parts = [str(part).strip() for part in parts if str(part).strip()]
    suffix = ":".join(normalized_parts)
    key = f"products:{namespace}:v{version}"
    if suffix:
        key = f"{key}:{suffix}"
    return key


def invalidate_catalog_cache() -> None:
    try:
        cache.incr(CATALOG_VERSION_KEY)
    except Exception:
        cache.set(CATALOG_VERSION_KEY, _new_version_value(), None)
