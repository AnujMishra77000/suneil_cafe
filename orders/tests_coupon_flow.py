from decimal import Decimal
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from cart.cache_store import set_cached_cart
from orders.models import CouponCode, Order, ServiceablePincode
from products.models import Category, Product, Section


class CouponFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.section = Section.objects.create(name=Section.SectionType.BAKERY)
        self.category = Category.objects.create(name="Bread", section=self.section)
        self.product = Product.objects.create(
            name="Milk Bread",
            category=self.category,
            price=Decimal("50.00"),
            stock_qty=30,
            image=SimpleUploadedFile("bread.jpg", b"image-bytes", content_type="image/jpeg"),
        )
        ServiceablePincode.objects.create(code="400001", area_name="Test Area", is_active=True)
        CouponCode.objects.update_or_create(code="RESIDENT10", defaults={"is_active": True})
        CouponCode.objects.update_or_create(code="RMC10", defaults={"is_active": True})
        CouponCode.objects.update_or_create(code="QUICK15", defaults={"is_active": True})

    def test_coupon_validation_endpoint_returns_discount_percent(self):
        response = self.client.post(
            "/api/orders/coupons/validate/",
            {"coupon_code": "resident10"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["coupon_code"], "RESIDENT10")
        self.assertEqual(response.data["discount_percent"], 10)

    def test_cart_checkout_applies_coupon_discount(self):
        cart_phone = "9123456789"
        set_cached_cart(cart_phone, {str(self.product.id): 2})

        response = self.client.post(
            "/api/cart/place/",
            {
                "phone": "9876543210",
                "customer_name": "Coupon User",
                "whatsapp_no": "9876543210",
                "address": "Test Street 400001",
                "pincode": "400001",
                "cart_phone": cart_phone,
                "coupon_code": "RMC10",
                "idempotency_key": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        order = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(order.coupon_code, "RMC10")
        self.assertEqual(order.subtotal_price, Decimal("100.00"))
        self.assertEqual(order.discount_percent, 10)
        self.assertEqual(order.discount_amount, Decimal("10.00"))
        self.assertEqual(order.total_price, Decimal("90.00"))

        user_bill = order.bills.get(recipient_type="USER")
        self.assertEqual(user_bill.subtotal_amount, Decimal("100.00"))
        self.assertEqual(user_bill.discount_amount, Decimal("10.00"))
        self.assertEqual(user_bill.total_amount, Decimal("90.00"))

    def test_direct_order_api_applies_coupon_discount(self):
        response = self.client.post(
            "/api/orders/place-order/",
            {
                "customer_name": "Quick Order",
                "phone": "9998887776",
                "whatsapp_no": "9998887776",
                "address": "Quick Lane 400001",
                "pincode": "400001",
                "coupon_code": "QUICK15",
                "idempotency_key": str(uuid4()),
                "items": [
                    {
                        "product_id": self.product.id,
                        "quantity": 2,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        order = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(order.coupon_code, "QUICK15")
        self.assertEqual(order.subtotal_price, Decimal("100.00"))
        self.assertEqual(order.discount_percent, 15)
        self.assertEqual(order.discount_amount, Decimal("15.00"))
        self.assertEqual(order.total_price, Decimal("85.00"))

    def test_cart_checkout_adds_delivery_charge_for_order_below_100(self):
        cart_phone = "9000000011"
        set_cached_cart(cart_phone, {str(self.product.id): 1})

        response = self.client.post(
            "/api/cart/place/",
            {
                "phone": "9000000099",
                "customer_name": "Delivery Charge User",
                "whatsapp_no": "9000000099",
                "address": "Charge Lane 400001",
                "pincode": "400001",
                "cart_phone": cart_phone,
                "coupon_code": "",
                "idempotency_key": str(uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        order = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(order.subtotal_price, Decimal("50.00"))
        self.assertEqual(order.discount_amount, Decimal("0.00"))
        self.assertEqual(order.total_price, Decimal("60.00"))

        admin_bill = order.bills.get(recipient_type="ADMIN")
        self.assertEqual(admin_bill.subtotal_amount, Decimal("50.00"))
        self.assertEqual(admin_bill.discount_amount, Decimal("0.00"))
        self.assertEqual(admin_bill.total_amount, Decimal("60.00"))
