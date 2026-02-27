from decimal import Decimal
from urllib.parse import quote

from django.conf import settings

from .models import Notification


def _safe_phone(raw_value):
    return str(raw_value or "").strip()


def _to_amount(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def get_admin_identifier():
    # Use explicit admin phone first, then Twilio sender as fallback, then static key.
    return (
        _safe_phone(getattr(settings, "ADMIN_PHONE", ""))
        or _safe_phone(getattr(settings, "TWILIO_PHONE_NUMBER", ""))
        or "ADMIN"
    )


def _items_payload(order):
    items = []
    for item in order.items.select_related("product").all():
        unit_price = _to_amount(item.price)
        quantity = int(item.quantity or 0)
        line_total = unit_price * quantity
        items.append(
            {
                "product_name": item.product.name,
                "quantity": quantity,
                "price": str(unit_price),
                "line_total": str(line_total),
            }
        )
    return items


def _lines_for_message(items):
    if not items:
        return "No line items found."
    return "\n".join(
        f"- {row['product_name']} x{row['quantity']} @ Rs {row['price']} (Rs {row['line_total']})"
        for row in items
    )


def _event_label(event_type):
    if event_type == Notification.EventType.ORDER_CONFIRMED:
        return "Order Confirmed"
    return "Order Placed"


def _customer_phone(order):
    return _safe_phone(order.phone) or _safe_phone(getattr(order.customer, "phone", ""))


def _customer_name(order):
    return str(order.customer_name or getattr(order.customer, "name", "") or "Guest Customer").strip()


def _bill_context(order, customer_phone):
    bill_map = {bill.recipient_type: bill.id for bill in order.bills.all()}
    user_bill_id = bill_map.get("USER")
    admin_bill_id = bill_map.get("ADMIN")

    user_download_url = ""
    if user_bill_id and customer_phone:
        user_download_url = f"/api/orders/bills/{user_bill_id}/download/?phone={quote(customer_phone)}"

    admin_bill_url = "/admin-dashboard/billing/"
    if admin_bill_id:
        admin_bill_url = f"/admin-dashboard/billing/{admin_bill_id}/"

    return {
        "user_bill_id": user_bill_id,
        "admin_bill_id": admin_bill_id,
        "user_download_url": user_download_url,
        "admin_bill_url": admin_bill_url,
    }


def create_order_notifications(order, event_type=Notification.EventType.ORDER_PLACED):
    customer_phone = _customer_phone(order)
    customer_name = _customer_name(order)
    owner_phone = get_admin_identifier()
    items = _items_payload(order)
    total_price = str(_to_amount(order.total_price))
    event_label = _event_label(event_type)
    bill_ctx = _bill_context(order, customer_phone)

    user_message = (
        f"{event_label} | Order #{order.id}\n"
        f"Customer: {customer_name}\n"
        f"{_lines_for_message(items)}\n"
        f"Total: Rs {total_price}\n"
        f"Owner Phone: {owner_phone}"
    )
    admin_message = (
        f"{event_label} | Order #{order.id}\n"
        f"Customer: {customer_name}\n"
        f"{_lines_for_message(items)}\n"
        f"Total: Rs {total_price}\n"
        f"Customer Phone: {customer_phone}"
    )

    common_payload = {
        "order_id": order.id,
        "event_type": event_type,
        "total_price": total_price,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "owner_phone": owner_phone,
        "items": items,
        "user_bill_id": bill_ctx["user_bill_id"],
        "admin_bill_id": bill_ctx["admin_bill_id"],
    }

    recipients = [
        {
            "recipient_type": Notification.RecipientType.USER,
            "recipient_identifier": customer_phone,
            "title": f"{event_label} - #{order.id}",
            "message": user_message,
            "payload": {
                **common_payload,
                "download_url": bill_ctx["user_download_url"],
                "download_label": "Download",
            },
        },
        {
            "recipient_type": Notification.RecipientType.ADMIN,
            "recipient_identifier": owner_phone,
            "title": f"{event_label} - #{order.id}",
            "message": admin_message,
            "payload": {
                **common_payload,
                "bill_url": bill_ctx["admin_bill_url"],
                "bill_label": "Bill",
            },
        },
    ]

    recipient_pairs = {
        (row["recipient_type"], row["recipient_identifier"])
        for row in recipients
        if row["recipient_identifier"]
    }
    existing_pairs = set(
        Notification.objects.filter(
            order=order,
            event_type=event_type,
            recipient_type__in=[pair[0] for pair in recipient_pairs] or [None],
            recipient_identifier__in=[pair[1] for pair in recipient_pairs] or [None],
        ).values_list("recipient_type", "recipient_identifier")
    )

    created_rows = []
    for row in recipients:
        pair = (row["recipient_type"], row["recipient_identifier"])
        if not row["recipient_identifier"] or pair in existing_pairs:
            continue

        created_rows.append(
            Notification(
                order=order,
                recipient_type=row["recipient_type"],
                recipient_identifier=row["recipient_identifier"],
                event_type=event_type,
                title=row["title"],
                message=row["message"],
                payload=row["payload"],
            )
        )

    if created_rows:
        Notification.objects.bulk_create(created_rows)

    return created_rows
