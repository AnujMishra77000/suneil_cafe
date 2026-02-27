from django.db import migrations, models, transaction


def _normalize_phone(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def _fallback_phone(customer_id, used):
    candidate = f"9{int(customer_id):09d}"[-10:]
    while candidate in used:
        candidate = str((int(candidate) + 1) % 10_000_000_000).zfill(10)
    return candidate


def _merge_cart_rows(db_alias, Cart, CartItem, primary_id, duplicate_id):
    primary_cart = Cart.objects.using(db_alias).filter(customer_id=primary_id).first()
    duplicate_cart = Cart.objects.using(db_alias).filter(customer_id=duplicate_id).first()

    if not duplicate_cart:
        return

    if not primary_cart:
        Cart.objects.using(db_alias).filter(pk=duplicate_cart.pk).update(customer_id=primary_id)
        return

    dup_items = list(CartItem.objects.using(db_alias).filter(cart_id=duplicate_cart.id))
    for dup_item in dup_items:
        existing = CartItem.objects.using(db_alias).filter(
            cart_id=primary_cart.id,
            product_id=dup_item.product_id,
        ).first()
        if existing:
            CartItem.objects.using(db_alias).filter(pk=existing.pk).update(
                quantity=existing.quantity + dup_item.quantity
            )
            CartItem.objects.using(db_alias).filter(pk=dup_item.pk).delete()
        else:
            CartItem.objects.using(db_alias).filter(pk=dup_item.pk).update(cart_id=primary_cart.id)

    Cart.objects.using(db_alias).filter(pk=duplicate_cart.pk).delete()


def dedupe_customers(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Customer = apps.get_model("users", "Customer")
    Cart = apps.get_model("cart", "Cart")
    CartItem = apps.get_model("cart", "CartItem")
    Order = apps.get_model("orders", "Order")

    with transaction.atomic(using=db_alias):
        customers = list(Customer.objects.using(db_alias).order_by("id"))
        primary_by_phone = {}
        used_phones = set()

        for customer in customers:
            normalized = _normalize_phone(customer.phone)
            if not normalized or normalized in used_phones and normalized not in primary_by_phone:
                normalized = _fallback_phone(customer.id, used_phones)

            primary = primary_by_phone.get(normalized)
            if primary is None:
                updates = {}
                if customer.phone != normalized:
                    updates["phone"] = normalized
                if customer.whatsapp_no:
                    normalized_wa = _normalize_phone(customer.whatsapp_no)
                    if normalized_wa and customer.whatsapp_no != normalized_wa:
                        updates["whatsapp_no"] = normalized_wa
                elif normalized:
                    updates["whatsapp_no"] = normalized

                if updates:
                    Customer.objects.using(db_alias).filter(pk=customer.pk).update(**updates)
                    for field, value in updates.items():
                        setattr(customer, field, value)

                primary_by_phone[normalized] = customer
                used_phones.add(normalized)
                continue

            primary_updates = {}
            if not primary.name and customer.name:
                primary_updates["name"] = customer.name
            if not primary.address and customer.address:
                primary_updates["address"] = customer.address
            if not primary.whatsapp_no and customer.whatsapp_no:
                wa = _normalize_phone(customer.whatsapp_no)
                if wa:
                    primary_updates["whatsapp_no"] = wa
            if primary_updates:
                Customer.objects.using(db_alias).filter(pk=primary.pk).update(**primary_updates)
                for field, value in primary_updates.items():
                    setattr(primary, field, value)

            _merge_cart_rows(db_alias, Cart, CartItem, primary.id, customer.id)
            Order.objects.using(db_alias).filter(customer_id=customer.id).update(customer_id=primary.id)
            Customer.objects.using(db_alias).filter(pk=customer.id).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_alter_customer_phone"),
        ("cart", "0002_alter_cartitem_unique_together_alter_cart_created_at_and_more"),
        ("orders", "0008_remove_orderitem_orders_orde_order_i_52f79a_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(dedupe_customers, noop_reverse),
        migrations.AlterField(
            model_name="customer",
            name="phone",
            field=models.CharField(db_index=True, max_length=15, unique=True),
        ),
    ]
