from cart.models import Cart, CartItem
from users.models import Customer


def resolve_primary_customer(phone, customer_name=None, whatsapp_no=None, create_if_missing=True):
    customers = Customer.objects.filter(phone=phone).only("id", "name", "phone", "whatsapp_no").order_by("id")
    primary = customers.first()

    if not primary:
        if not create_if_missing:
            return None
        return Customer.objects.create(
            name=customer_name or "Guest Customer",
            phone=phone,
            whatsapp_no=whatsapp_no or phone,
        )

    updated = False
    if customer_name and not primary.name:
        primary.name = customer_name
        updated = True
    if whatsapp_no and not primary.whatsapp_no:
        primary.whatsapp_no = whatsapp_no
        updated = True
    if updated:
        primary.save(update_fields=["name", "whatsapp_no"])

    return primary


def merge_phone_carts(phone, customer_name=None, whatsapp_no=None, create_if_missing=True):
    primary = resolve_primary_customer(
        phone=phone,
        customer_name=customer_name,
        whatsapp_no=whatsapp_no,
        create_if_missing=create_if_missing,
    )
    if not primary:
        return None, None

    primary_cart, _ = Cart.objects.get_or_create(customer=primary)

    duplicate_ids = list(
        Customer.objects.filter(phone=phone).exclude(pk=primary.pk).values_list("id", flat=True)[:50]
    )
    if not duplicate_ids:
        return primary, primary_cart

    duplicate_carts = Cart.objects.filter(customer_id__in=duplicate_ids).prefetch_related("items__product")
    for duplicate_cart in duplicate_carts:
        if not duplicate_cart:
            continue

        for dup_item in duplicate_cart.items.all():
            primary_item, created = CartItem.objects.get_or_create(
                cart=primary_cart,
                product=dup_item.product,
                defaults={"quantity": dup_item.quantity},
            )
            if not created:
                primary_item.quantity += dup_item.quantity
                primary_item.save(update_fields=["quantity"])

        duplicate_cart.delete()

    return primary, primary_cart


def get_primary_customer_and_cart(phone, create_if_missing=False):
    """
    Fast path for read-heavy endpoints:
    - resolve primary customer by phone
    - return that customer's cart
    - does NOT merge duplicate carts (keeps request latency low)
    """
    primary = resolve_primary_customer(
        phone=phone,
        create_if_missing=create_if_missing,
    )
    if not primary:
        return None, None

    cart = Cart.objects.filter(customer=primary).first()
    if create_if_missing and not cart:
        cart = Cart.objects.create(customer=primary)
    return primary, cart


def get_or_create_cart_for_phone(phone):
    """
    Ultra-fast path for add-to-cart:
    - pick/create primary customer by phone
    - pick/create cart
    - skip duplicate-cart merge (expensive)
    """
    primary = Customer.objects.filter(phone=phone).only("id").order_by("id").first()
    if not primary:
        primary = Customer.objects.create(
            name="Guest Customer",
            phone=phone,
            whatsapp_no=phone,
        )

    cart = Cart.objects.filter(customer_id=primary.id).only("id", "customer_id").first()
    if not cart:
        cart = Cart.objects.create(customer=primary)

    return primary, cart
