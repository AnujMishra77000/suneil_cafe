from contextlib import contextmanager, nullcontext

from django.core.cache import cache


@contextmanager
def cart_write_lock(phone: str, timeout: int = 5, blocking_timeout: int = 2):
    """
    Distributed lock for cart writes.

    In production with django-redis, `cache.lock` is cross-process and helps
    prevent lost updates when concurrent add/update/remove calls hit same cart.
    """
    lock_factory = getattr(cache, "lock", None)
    lock_name = f"lock:cart:phone:{phone}"

    if callable(lock_factory):
        lock = lock_factory(lock_name, timeout=timeout, blocking_timeout=blocking_timeout)
        with lock:
            yield
        return

    with nullcontext():
        yield
