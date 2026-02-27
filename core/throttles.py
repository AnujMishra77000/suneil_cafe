from rest_framework.throttling import ScopedRateThrottle


class CartAddRateThrottle(ScopedRateThrottle):
    scope = "cart_add"


class CheckoutPlaceRateThrottle(ScopedRateThrottle):
    scope = "checkout_place"


class OrderHistoryRateThrottle(ScopedRateThrottle):
    scope = "order_history"


class BuyNowRateThrottle(ScopedRateThrottle):
    scope = "buy_now"
