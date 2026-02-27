from django.core.cache import cache
from products.models import Product


def _anon_cart_key(phone):
    return f"cart:anon:v1:{phone}"


def get_cached_cart(phone):
    data = cache.get(_anon_cart_key(phone))
    if not isinstance(data, dict):
        return {}

    normalized = {}
    for k, v in data.items():
        try:
            pid = str(int(k))
            qty = int(v)
            if qty > 0:
                normalized[pid] = qty
        except Exception:
            continue
    return normalized


def set_cached_cart(phone, cart_map, timeout=60 * 60 * 24):
    safe = {}
    for k, v in (cart_map or {}).items():
        try:
            pid = str(int(k))
            qty = int(v)
            if qty > 0:
                safe[pid] = qty
        except Exception:
            continue
    cache.set(_anon_cart_key(phone), safe, timeout)
    return safe


def clear_cached_cart(phone):
    cache.delete(_anon_cart_key(phone))


def build_payload_from_cached_cart(phone, request=None):
    cart_map = get_cached_cart(phone)
    if not cart_map:
        return {"items": [], "total_items": 0, "total_amount": "0.00"}

    product_ids = [int(pid) for pid in cart_map.keys()]
    products = Product.objects.filter(id__in=product_ids).only(
        "id", "name", "price", "image", "stock_qty", "is_available"
    )
    product_map = {p.id: p for p in products}

    items = []
    total_items = 0
    total_amount = 0
    cleaned = {}

    for pid_text, qty in cart_map.items():
        pid = int(pid_text)
        product = product_map.get(pid)
        if not product:
            continue

        safe_qty = min(qty, product.stock_qty) if product.stock_qty >= 0 else qty
        if safe_qty <= 0:
            continue

        cleaned[str(pid)] = safe_qty
        line_total = product.price * safe_qty
        image = None
        if product.image:
            if request:
                image = request.build_absolute_uri(product.image.url)
            else:
                image = product.image.url

        items.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "price": str(product.price),
                "quantity": safe_qty,
                "image": image,
                "line_total": str(line_total),
            }
        )
        total_items += safe_qty
        total_amount += line_total

    if cleaned != cart_map:
        set_cached_cart(phone, cleaned)

    items.sort(key=lambda x: x["product_name"].lower())
    return {
        "items": items,
        "total_items": total_items,
        "total_amount": str(total_amount),
    }
