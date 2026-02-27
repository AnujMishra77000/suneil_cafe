from django.db import transaction
from django.db.models import F, Case, When, Value, BooleanField
from products.cache_utils import invalidate_catalog_cache
from products.models import Product
from users.customer_resolver import resolve_primary_customer
from .models import Order, OrderItem, Bill, BillItem, SalesRecord
from .tasks import send_order_notifications
from .pincode_service import ensure_serviceable_pincode

# for notification system
from notifications.services import create_order_notifications

def create_bills_for_order(order):
    user_bill = Bill.objects.create(
        order=order,
        recipient_type='USER',
        bill_number=f"ORD-{order.id}-U",
        customer_name=order.customer_name or order.customer.name,
        phone=order.phone or order.customer.phone,
        shipping_address=order.shipping_address,
        total_amount=order.total_price,
    )
    admin_bill = Bill.objects.create(
        order=order,
        recipient_type='ADMIN',
        bill_number=f"ORD-{order.id}-A",
        customer_name=order.customer_name or order.customer.name,
        phone=order.phone or order.customer.phone,
        shipping_address=order.shipping_address,
        total_amount=order.total_price,
    )
    order_items = list(order.items.select_related("product").all())
    for item in order_items:
        BillItem.objects.create(
            bill=user_bill,
            product_name=item.product.name,
            quantity=item.quantity,
            unit_price=item.price,
        )
        BillItem.objects.create(
            bill=admin_bill,
            product_name=item.product.name,
            quantity=item.quantity,
            unit_price=item.price,
        )
    return user_bill, admin_bill


def create_sales_records_for_order(order):
    rows = []
    for item in order.items.select_related("product__category").all():
        rows.append(
            SalesRecord(
                order=order,
                category=item.product.category.name,
                product_name=item.product.name,
                price=item.price,
                quantity=item.quantity,
            )
        )
    if rows:
        SalesRecord.objects.bulk_create(rows)
def create_order(validated_data):
    items_data = validated_data.pop('items')
    customer_name = validated_data.pop('customer_name')
    phone = validated_data.pop('phone')
    whatsapp_no = validated_data.pop('whatsapp_no')
    address = validated_data.pop('address')
    pincode = validated_data.pop('pincode', '')

    ensure_serviceable_pincode(pincode=pincode, address=address)

    # 🔒 Atomic transaction (Rollback safety)
    with transaction.atomic():

        # 1️⃣ Create / Get Customer
        customer = resolve_primary_customer(
            phone=phone,
            customer_name=customer_name,
            whatsapp_no=whatsapp_no,
            create_if_missing=True,
        )
        customer.name = customer_name
        customer.whatsapp_no = whatsapp_no
        customer.address = address
        customer.save(update_fields=["name", "whatsapp_no", "address"])

        total_price = 0
        order_items = []

        # 2️⃣ Lock rows so no other user can buy same stock
        product_ids = [item['product_id'] for item in items_data]
        products = Product.objects.select_for_update().filter(id__in=product_ids)

        products_dict = {p.id: p for p in products}

        # 3️⃣ Validate stock again inside transaction
        for item in items_data:
            product = products_dict.get(item['product_id'])

            if not product:
                raise Exception("Product not found")

            if product.stock_qty < item['quantity']:
                raise Exception(f"{product.name} is out of stock")

            price = product.price * item['quantity']
            total_price += price

            order_items.append({
                'product': product,
                'quantity': item['quantity'],
                'price': product.price
            })

        # 4️⃣ Create Order
        order = Order.objects.create(
            customer=customer,
            customer_name=customer_name,
            phone=phone,
            shipping_address=address,
            total_price=total_price,
            status='Placed'
        )
        

        # 5️⃣ Create Order Items + Deduct Stock
        for item in order_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                price=item['price']
            )

            # Stock deduction using F expression (safe in concurrency)
            Product.objects.filter(pk=item['product'].pk).update(
                stock_qty=F('stock_qty') - item['quantity'],
                is_available=Case(
                    When(stock_qty__gt=item['quantity'], then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
        invalidate_catalog_cache()
        create_bills_for_order(order)
        create_sales_records_for_order(order)
        create_order_notifications(order, event_type='ORDER_PLACED')
        send_order_notifications.delay(order.id)
        
        return order
        


# 💥 EXAMPLE FLOW
# If 2 users try to buy last 1 cake:
# User A locks row → stock becomes 0
# User B waits → stock check fails → rollback

# NO double selling possible ✅
    




@transaction.atomic
def create_order_from_cart(user, cart):

    # 1️⃣ Create Order
    order = Order.objects.create(
        customer=user,
        total_amount=cart.get_total_price(),
        status='PLACED'
    )

    # 2️⃣ Create Order Items
    for item in cart.items.all():
        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=item.product.price
        )

    # 3️⃣ Create Notifications (DB only, no SMS yet)
    create_bills_for_order(order)
    create_order_notifications(order)

    return order
