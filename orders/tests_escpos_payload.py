import os
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from orders.escpos_usb import _build_payload
from orders.models import Bill, BillItem, Order
from users.models import Customer


class EscPosPayloadTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Sunil Shetty",
            phone="9867616095",
            whatsapp_no="9867616095",
            address="Runwal, Dombivli East",
        )
        self.order = Order.objects.create(
            customer=self.customer,
            customer_name="Sunil Shetty",
            phone="9867616095",
            shipping_address="701, Tower 1, Runwal Mycity, Dombivli East, Thane",
            subtotal_price=Decimal("35.00"),
            discount_amount=Decimal("0.00"),
            total_price=Decimal("45.00"),
            status="Placed",
        )
        self.bill = Bill.objects.create(
            order=self.order,
            recipient_type="ADMIN",
            bill_number="ORD-16-A",
            customer_name="Sunil Shetty",
            phone="9867616095",
            shipping_address="701, Tower 1, Runwal Mycity, Dombivli East, Thane",
            subtotal_amount=Decimal("35.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("45.00"),
            coupon_code="",
            discount_percent=0,
        )
        BillItem.objects.create(
            bill=self.bill,
            product_name="Raisin Bagel",
            quantity=1,
            unit_price=Decimal("35.00"),
        )

    def test_payload_contains_full_bill_details(self):
        with patch.dict(os.environ, {"ESC_POS_PRINT_LOGO": "false"}, clear=False):
            payload = _build_payload(self.bill)
        text = payload.decode("ascii", "ignore")

        self.assertIn("THATHWAMASI BAKERY CAFE", text)
        self.assertIn("Bill No: ORD-16-A", text)
        self.assertIn("Status: Placed", text)
        self.assertIn("Customer: Sunil Shetty", text)
        self.assertIn("Raisin Bagel", text)
        self.assertIn("Subtotal: 35.00", text)
        self.assertIn("Delivery: 10.00", text)
        self.assertIn("Grand Total: 45.00", text)
