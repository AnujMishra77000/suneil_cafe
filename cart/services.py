from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Case, F, Value, When

from cart.cache_store import clear_cached_cart, get_cached_cart
from cart.models import Cart, CartItem
from notifications.services import create_order_notifications
from orders.models import Order, OrderItem
from orders.pincode_service import ensure_serviceable_pincode
from orders.services import create_bills_for_order, create_sales_records_for_order
from orders.tasks import send_order_notifications
from products.cache_utils import invalidate_catalog_cache
from products.models import Product
from users.customer_resolver import merge_phone_carts
from users.phone_utils import normalize_phone


@transaction.atomic
def convert_cart_to_order(data):
    idempotency_key = data["idempotency_key"]
    existing = Order.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    phone = normalize_phone(data["phone"])
    name = data["customer_name"]
    whatsapp_no = normalize_phone(data.get("whatsapp_no") or phone)
    address = data["address"]
    pincode = data.get("pincode", "")
    source_phone = normalize_phone(data.get("cart_phone") or phone)

    ensure_serviceable_pincode(pincode=pincode, address=address)

    cached_map = get_cached_cart(source_phone)
    if cached_map:
        customer, _ = merge_phone_carts(
            phone=phone,
            customer_name=name,
            whatsapp_no=whatsapp_no,
            create_if_missing=True,
        )

        customer.name = name
        customer.whatsapp_no = whatsapp_no
        customer.address = address
        customer.save(update_fields=["name", "whatsapp_no", "address"])

        total_price = 0
        products = []
        product_ids = [int(pid) for pid in cached_map.keys()]
        product_qs = Product.objects.select_for_update().filter(id__in=product_ids)
        product_map = {p.id: p for p in product_qs}

        for pid_text, qty in cached_map.items():
            pid = int(pid_text)
            product = product_map.get(pid)
            if not product:
                continue
            if product.stock_qty < qty:
                raise Exception(f"{product.name} out of stock")
            total_price += product.price * qty
            products.append((product, qty))

        if not products:
            raise Exception("Cart is empty")

        try:
            order = Order.objects.create(
                customer=customer,
                customer_name=name,
                phone=phone,
                shipping_address=address,
                idempotency_key=idempotency_key,
                total_price=total_price,
            )
        except IntegrityError:
            existing = Order.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
            raise

        for product, qty in products:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                price=product.price,
            )
            Product.objects.filter(pk=product.pk).update(
                stock_qty=F("stock_qty") - qty,
                is_available=Case(
                    When(stock_qty__gt=qty, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )

        clear_cached_cart(source_phone)
        if source_phone != phone:
            clear_cached_cart(phone)

        invalidate_catalog_cache()
        create_bills_for_order(order)
        create_sales_records_for_order(order)
        create_order_notifications(order, event_type="ORDER_PLACED")
        send_order_notifications.delay(order.id)
        return order

    customer, cart = None, None
    if source_phone != phone:
        # Merge guest/anonymous cart into real customer cart by phone.
        _, source_cart = merge_phone_carts(
            phone=source_phone,
            create_if_missing=False,
        )
        customer, cart = merge_phone_carts(
            phone=phone,
            customer_name=name,
            whatsapp_no=whatsapp_no,
            create_if_missing=True,
        )
        if source_cart:
            source_items = source_cart.items.select_related("product")
            for src_item in source_items:
                target_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=src_item.product,
                    defaults={"quantity": src_item.quantity},
                )
                if not created:
                    target_item.quantity += src_item.quantity
                    target_item.save(update_fields=["quantity"])
            source_cart.delete()
    else:
        customer, cart = merge_phone_carts(
            phone=phone,
            customer_name=name,
            whatsapp_no=whatsapp_no,
            create_if_missing=True,
        )

    if not cart:
        raise Exception("Cart not found")

    customer.name = name
    customer.whatsapp_no = whatsapp_no
    customer.address = address
    customer.save(update_fields=["name", "whatsapp_no", "address"])

    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    cart_items = cart.items.select_related("product")

    if not cart_items.exists():
        raise Exception("Cart is empty")

    total_price = 0
    products = []

    # Lock product rows
    product_ids = [item.product.id for item in cart_items]
    product_qs = Product.objects.select_for_update().filter(id__in=product_ids)
    product_map = {p.id: p for p in product_qs}

    # Validate stock
    for item in cart_items:
        product = product_map[item.product.id]

        if product.stock_qty < item.quantity:
            raise Exception(f"{product.name} out of stock")

        total_price += product.price * item.quantity
        products.append((product, item.quantity))

    try:
        order = Order.objects.create(
            customer=customer,
            customer_name=name,
            phone=phone,
            shipping_address=address,
            idempotency_key=idempotency_key,
            total_price=total_price,
        )
    except IntegrityError:
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
        raise

    # Create order items + deduct stock
    for product, qty in products:
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=qty,
            price=product.price,
        )

        Product.objects.filter(pk=product.pk).update(
            stock_qty=F("stock_qty") - qty,
            is_available=Case(
                When(stock_qty__gt=qty, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )

    # Clear cart
    cart.items.all().delete()

    invalidate_catalog_cache()

    # Async notification
    create_bills_for_order(order)
    create_sales_records_for_order(order)
    create_order_notifications(order, event_type="ORDER_PLACED")
    send_order_notifications.delay(order.id)

    return order
