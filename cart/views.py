from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce
from users.customer_resolver import (
    merge_phone_carts,
    get_primary_customer_and_cart,
)
from core.throttles import CartAddRateThrottle
from products.models import Product
from .models import Cart, CartItem
from .cache_store import (
    get_cached_cart,
    set_cached_cart,
    clear_cached_cart,
    build_payload_from_cached_cart,
)
from .serializers import (
    AddToCartSerializer,
    CartSerializer,
    PlaceOrderSerializer,
    UpdateCartItemSerializer,
    RemoveCartItemSerializer,
)
from .locks import cart_write_lock
from .services import convert_cart_to_order


class PublicAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]



class AddToCartAPIView(PublicAPIView):
    throttle_classes = [CartAddRateThrottle]
    throttle_scope = "cart_add"

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data["quantity"]

        try:
            # Distributed lock prevents lost updates on concurrent cart writes.
            with cart_write_lock(phone):
                cart_map = get_cached_cart(phone)
                current_qty = int(cart_map.get(str(product_id), 0))
                next_qty = current_qty + quantity
                if next_qty > 99:
                    return Response({"error": "Max 99 quantity per item"}, status=400)

                cart_map[str(product_id)] = next_qty
                set_cached_cart(phone, cart_map)

            return Response({"message": "Added to cart"})
        except Exception as exc:
            return Response({"error": str(exc)}, status=400)


class ViewCartAPIView(PublicAPIView):
    def get(self, request):
        phone = request.GET.get("phone")

        if not phone:
            return Response({"error": "Phone required"}, status=400)

        # Cart is user-specific and write-heavy; avoid response caching for consistency.
        anon_payload = build_payload_from_cached_cart(phone, request=request)
        if anon_payload["total_items"] > 0:
            return Response(anon_payload)

        customer, cart = get_primary_customer_and_cart(
            phone=phone,
            create_if_missing=False,
        )
        if not customer:
            payload = {"items": [], "total_items": 0, "total_amount": "0.00"}
            return Response(payload)

        if not cart:
            payload = {"items": [], "total_items": 0, "total_amount": "0.00"}
            return Response(payload)

        cart = (
            Cart.objects.filter(pk=cart.pk)
            # Fetch item + product rows up-front for serializer to avoid N+1.
            .prefetch_related("items__product")
            .annotate(
                total_items=Coalesce(Sum("items__quantity"), 0),
                total_amount=Coalesce(
                    Sum(
                        F("items__quantity") * F("items__product__price"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    ),
                    Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .first()
        )

        serializer = CartSerializer(cart, context={"request": request})
        payload = serializer.data
        return Response(payload)


class UpdateCartItemAPIView(PublicAPIView):
    def post(self, request):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data["quantity"]

        with cart_write_lock(phone):
            cart_map = get_cached_cart(phone)
            if cart_map:
                pid = str(product_id)
                if quantity == 0:
                    if pid in cart_map:
                        del cart_map[pid]
                        set_cached_cart(phone, cart_map)
                    return Response({"message": "Item removed"})

                if quantity > 99:
                    return Response({"error": "Max 99 quantity per item"}, status=400)

                cart_map[pid] = quantity
                set_cached_cart(phone, cart_map)
                return Response({"message": "Cart updated"})

        customer, cart = get_primary_customer_and_cart(
            phone=phone,
            create_if_missing=False,
        )
        if not customer:
            return Response({"error": "Customer not found"}, status=404)

        if not cart:
            return Response({"error": "Cart not found"}, status=404)

        with transaction.atomic():
            cart = Cart.objects.select_for_update().filter(pk=cart.pk).first()
            if not cart:
                return Response({"error": "Cart not found"}, status=404)

            item = CartItem.objects.select_for_update().filter(cart=cart, product_id=product_id).first()
            if not item:
                # Fallback once for legacy duplicate carts created before phone-dedupe fix.
                _, merged_cart = merge_phone_carts(phone=phone, create_if_missing=False)
                if merged_cart:
                    cart = Cart.objects.select_for_update().filter(pk=merged_cart.pk).first()
                    item = CartItem.objects.select_for_update().filter(cart=cart, product_id=product_id).first()
            if not item:
                return Response({"error": "Cart item not found"}, status=404)

            if quantity == 0:
                item.delete()
                return Response({"message": "Item removed"})

            product = Product.objects.select_for_update().filter(id=product_id).first()
            if not product:
                return Response({"error": "Product not found"}, status=404)
            if product.stock_qty < quantity:
                return Response({"error": f"Only {product.stock_qty} in stock"}, status=400)

            item.quantity = quantity
            item.save(update_fields=["quantity"])

        return Response({"message": "Cart updated"})


class RemoveCartItemAPIView(PublicAPIView):
    def post(self, request):
        serializer = RemoveCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        product_id = serializer.validated_data["product_id"]

        with cart_write_lock(phone):
            cart_map = get_cached_cart(phone)
            if cart_map:
                pid = str(product_id)
                if pid not in cart_map:
                    return Response({"error": "Cart item not found"}, status=404)
                del cart_map[pid]
                set_cached_cart(phone, cart_map)
                return Response({"message": "Item removed"})

        customer, cart = get_primary_customer_and_cart(
            phone=phone,
            create_if_missing=False,
        )
        if not customer:
            return Response({"error": "Customer not found"}, status=404)

        if not cart:
            return Response({"error": "Cart not found"}, status=404)

        with transaction.atomic():
            cart = Cart.objects.select_for_update().filter(pk=cart.pk).first()
            item = CartItem.objects.select_for_update().filter(cart=cart, product_id=product_id).first()
            if not item:
                # Fallback once for legacy duplicate carts created before phone-dedupe fix.
                _, merged_cart = merge_phone_carts(phone=phone, create_if_missing=False)
                if merged_cart:
                    cart = Cart.objects.select_for_update().filter(pk=merged_cart.pk).first()
                    item = CartItem.objects.select_for_update().filter(cart=cart, product_id=product_id).first()
            if not item:
                return Response({"error": "Cart item not found"}, status=404)

            item.delete()

        return Response({"message": "Item removed"})


class PlaceOrderAPIView(PublicAPIView):

    def post(self, request):
        serializer = PlaceOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = convert_cart_to_order(serializer.validated_data)
            phone = serializer.validated_data["phone"]
            source_phone = serializer.validated_data.get("cart_phone") or phone
            clear_cached_cart(phone)
            if source_phone != phone:
                clear_cached_cart(source_phone)
            return Response({
                "message": "Order placed successfully",
                "order_id": order.id
            })
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class CartCacheDebugAPIView(PublicAPIView):
    """
    Debug endpoint for cache-backed anonymous carts.
    Security:
    - If CART_DEBUG_TOKEN is set, token is required via X-Debug-Token header or ?token=
    - If token is not set, only available when DEBUG=True
    """

    def _is_authorized(self, request):
        expected = (getattr(settings, "CART_DEBUG_TOKEN", "") or "").strip()
        provided = (
            request.headers.get("X-Debug-Token")
            or request.GET.get("token")
            or ""
        ).strip()
        if expected:
            return provided == expected
        return bool(getattr(settings, "DEBUG", False))

    def get(self, request):
        if not self._is_authorized(request):
            return Response({"detail": "Forbidden"}, status=403)

        pattern = request.GET.get("pattern", "cart:anon:v1:*")
        try:
            max_keys = int(request.GET.get("max_keys", 100))
        except (TypeError, ValueError):
            max_keys = 100
        max_keys = min(max(max_keys, 1), 2000)
        cache_backend = getattr(cache, "_cache", cache)
        configured_backend = (
            getattr(settings, "CACHES", {})
            .get("default", {})
            .get("BACKEND", "")
        )
        backend_name = cache_backend.__class__.__name__
        backend_path = f"{cache_backend.__class__.__module__}.{backend_name}"

        key_count = None
        key_samples = []
        truncated = False
        supports_key_scan = hasattr(cache_backend, "iter_keys")

        if supports_key_scan:
            for idx, key in enumerate(cache_backend.iter_keys(pattern)):
                if idx < max_keys:
                    key_samples.append(str(key))
                else:
                    truncated = True
                    break
            key_count = len(key_samples) + (1 if truncated else 0)

        phones = request.GET.get("phones", "").strip()
        preview = {}
        if phones:
            for phone in [p.strip() for p in phones.split(",") if p.strip()][:20]:
                preview[phone] = get_cached_cart(phone)

        return Response(
            {
                "cache_backend": backend_path,
                "cache_backend_configured": configured_backend,
                "supports_key_scan": supports_key_scan,
                "pattern": pattern,
                "key_count_estimate": key_count,
                "keys_sample": key_samples,
                "keys_truncated": truncated,
                "preview_by_phone": preview,
                "auth_mode": "token" if getattr(settings, "CART_DEBUG_TOKEN", "") else "debug_only",
            }
        )
