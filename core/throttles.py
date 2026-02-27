from rest_framework.throttling import ScopedRateThrottle


class CartAddRateThrottle(ScopedRateThrottle):
    scope = "cart_add"
