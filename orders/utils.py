def build_customer_message(order):
    items_text = ""
    for item in order.items.all():
        items_text += f"{item.product.name} x{item.quantity} = ₹{item.price * item.quantity}\n"

    message = (
        f"🧁 *Thank you for ordering from Thathwamasi Bakery Cafe!*\n\n"
        f"🧾 Order ID: {order.id}\n\n"
        f"📦 Your Items:\n{items_text}\n"
        f"💰 Total Amount: ₹{order.total_price}\n\n"
        f"🚚 Your order will be delivered within *30 minutes*.\n"
        f"📞 Shop Contact: 9XXXXXXXXX\n\n"
        f"🙏 Thank you for choosing us!"
    )

    return message


def build_admin_message(order):
    items_text = ""
    for item in order.items.all():
        items_text += f"{item.product.name} x{item.quantity}\n"

    message = (
        f"📢 *NEW ORDER RECEIVED*\n\n"
        f"👤 Customer: {order.customer.name}\n"
        f"📱 Phone: {order.customer.phone}\n\n"
        f"🧾 Items:\n{items_text}\n"
        f"💰 Total: ₹{order.total_price}"
    )

    return message
