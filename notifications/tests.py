from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from notifications.models import Notification
from notifications.services import create_order_notifications
from orders.models import Bill, BillItem, Order, OrderItem
from products.models import Category, Product, Section
from users.models import Customer


def _build_order(phone="9876543210", status="Placed"):
    section = Section.objects.create(name=Section.SectionType.BAKERY)
    category = Category.objects.create(name="Puff", section=section)
    product = Product.objects.create(
        name="Veg Puff",
        category=category,
        price=Decimal("25.00"),
        stock_qty=50,
        image=SimpleUploadedFile("veg-puff.jpg", b"binary-image", content_type="image/jpeg"),
    )
    customer = Customer.objects.create(
        name="Test User",
        phone=phone,
        whatsapp_no=phone,
        address="Mumbai",
    )
    order = Order.objects.create(
        customer=customer,
        customer_name=customer.name,
        phone=phone,
        shipping_address=customer.address,
        total_price=Decimal("50.00"),
        status=status,
    )
    OrderItem.objects.create(order=order, product=product, quantity=2, price=Decimal("25.00"))
    return order


def _create_bills_for_order(order):
    user_bill = Bill.objects.create(
        order=order,
        recipient_type="USER",
        bill_number=f"ORD-{order.id}-U",
        customer_name=order.customer_name,
        phone=order.phone,
        shipping_address=order.shipping_address,
        total_amount=order.total_price,
    )
    admin_bill = Bill.objects.create(
        order=order,
        recipient_type="ADMIN",
        bill_number=f"ORD-{order.id}-A",
        customer_name=order.customer_name,
        phone=order.phone,
        shipping_address=order.shipping_address,
        total_amount=order.total_price,
    )

    for item in order.items.select_related("product").all():
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


@override_settings(ADMIN_PHONE="7700010890")
class NotificationModuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.order = _build_order()
        self.user_bill, self.admin_bill = _create_bills_for_order(self.order)

    def test_order_placed_notification_contains_required_details(self):
        create_order_notifications(self.order, event_type=Notification.EventType.ORDER_PLACED)

        user_notification = Notification.objects.get(
            recipient_type=Notification.RecipientType.USER,
            recipient_identifier=self.order.phone,
            event_type=Notification.EventType.ORDER_PLACED,
        )
        admin_notification = Notification.objects.get(
            recipient_type=Notification.RecipientType.ADMIN,
            recipient_identifier="7700010890",
            event_type=Notification.EventType.ORDER_PLACED,
        )

        self.assertIn("Veg Puff", user_notification.message)
        self.assertIn("Owner Phone: 7700010890", user_notification.message)
        self.assertIn("Customer Phone: 9876543210", admin_notification.message)

        self.assertEqual(user_notification.payload["customer_name"], "Test User")
        self.assertEqual(user_notification.payload["total_price"], "50.00")
        self.assertTrue(user_notification.payload["download_url"].startswith("/api/orders/bills/"))
        self.assertEqual(user_notification.payload["user_bill_id"], self.user_bill.id)

        self.assertEqual(admin_notification.payload["admin_bill_id"], self.admin_bill.id)
        self.assertTrue(admin_notification.payload["bill_url"].startswith("/admin-dashboard/billing/"))

    def test_order_notification_is_not_duplicated_for_same_event(self):
        create_order_notifications(self.order, event_type=Notification.EventType.ORDER_PLACED)
        create_order_notifications(self.order, event_type=Notification.EventType.ORDER_PLACED)

        self.assertEqual(
            Notification.objects.filter(
                order=self.order,
                event_type=Notification.EventType.ORDER_PLACED,
            ).count(),
            2,
        )

    def test_order_confirmed_signal_creates_user_and_admin_notifications(self):
        self.order.status = "Confirmed"
        self.order.save(update_fields=["status"])

        self.assertEqual(
            Notification.objects.filter(
                order=self.order,
                event_type=Notification.EventType.ORDER_CONFIRMED,
            ).count(),
            2,
        )

    def test_user_feed_and_mark_read_flow(self):
        create_order_notifications(self.order, event_type=Notification.EventType.ORDER_PLACED)

        feed_resp = self.client.get(
            "/api/notifications/feed/",
            {
                "recipient_type": "USER",
                "recipient_identifier": self.order.phone,
            },
        )
        self.assertEqual(feed_resp.status_code, 200)
        self.assertEqual(feed_resp.data["unread_count"], 1)
        notification_id = feed_resp.data["notifications"][0]["id"]

        mark_resp = self.client.post(
            "/api/notifications/mark-read/",
            {
                "recipient_type": "USER",
                "recipient_identifier": self.order.phone,
                "notification_ids": [notification_id],
            },
            format="json",
        )
        self.assertEqual(mark_resp.status_code, 200)
        self.assertEqual(mark_resp.data["unread_count"], 0)

    def test_admin_feed_requires_staff_login(self):
        create_order_notifications(self.order, event_type=Notification.EventType.ORDER_PLACED)

        denied_resp = self.client.get(
            "/api/notifications/feed/",
            {
                "recipient_type": "ADMIN",
                "recipient_identifier": "7700010890",
            },
        )
        self.assertEqual(denied_resp.status_code, 403)

        user_model = get_user_model()
        staff_user = user_model.objects.create_user(
            username="admin_user",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        allowed_resp = self.client.get(
            "/api/notifications/feed/",
            {
                "recipient_type": "ADMIN",
            },
        )
        self.assertEqual(allowed_resp.status_code, 200)
        self.assertEqual(allowed_resp.data["unread_count"], 1)

    def test_user_bill_download_requires_matching_phone(self):
        good = self.client.get(f"/api/orders/bills/{self.user_bill.id}/download/?phone={self.order.phone}")
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good["Content-Type"], "application/pdf")

        bad = self.client.get(f"/api/orders/bills/{self.user_bill.id}/download/?phone=0000000000")
        self.assertEqual(bad.status_code, 404)
