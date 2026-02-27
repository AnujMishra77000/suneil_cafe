from cart.models import Cart, CartItem
from users.models import Customer
from users.phone_utils import normalize_phone


def resolve_primary_customer(phone, customer_name=None, whatsapp_no=None, create_if_missing=True):
    normalized_phone = normalize_phone(phone)
    normalized_whatsapp = normalize_phone(whatsapp_no or normalized_phone)

    customers = (
        Customer.objects.filter(phone=normalized_phone)
        .only("id", "name", "phone", "whatsapp_no")
        .order_by("id")
    )
    primary = customers.first()

    if not primary:
        if not create_if_missing:
            return None
        return Customer.objects.create(
            name=customer_name or "Guest Customer",
            phone=normalized_phone,
            whatsapp_no=normalized_whatsapp,
        )

    updated = False
    if customer_name and primary.name != customer_name:
        primary.name = customer_name
        updated = True
    if normalized_whatsapp and primary.whatsapp_no != normalized_whatsapp:
        primary.whatsapp_no = normalized_whatsapp
        updated = True
    if updated:
        primary.save(update_fields=["name", "whatsapp_no"])

    return primary


def merge_phone_carts(phone, customer_name=None, whatsapp_no=None, create_if_missing=True):
    normalized_phone = normalize_phone(phone)
    primary = resolve_primary_customer(
        phone=normalized_phone,
        customer_name=customer_name,
        whatsapp_no=whatsapp_no,
        create_if_missing=create_if_missing,
    )
    if not primary:
        return None, None

    primary_cart, _ = Cart.objects.get_or_create(customer=primary)

    duplicate_ids = list(
        Customer.objects.filter(phone=normalized_phone).exclude(pk=primary.pk).values_list("id", flat=True)[:50]
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
    normalized_phone = normalize_phone(phone)
    primary = resolve_primary_customer(
        phone=normalized_phone,
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
    normalized_phone = normalize_phone(phone)

    primary = Customer.objects.filter(phone=normalized_phone).only("id").order_by("id").first()
    if not primary:
        primary = Customer.objects.create(
            name="Guest Customer",
            phone=normalized_phone,
            whatsapp_no=normalized_phone,
        )

    cart = Cart.objects.filter(customer_id=primary.id).only("id", "customer_id").first()
    if not cart:
        cart = Cart.objects.create(customer=primary)

    return primary, cart
