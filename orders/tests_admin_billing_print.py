from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.models import Bill, BillItem, Order
from users.models import Customer


User = get_user_model()


class AdminBillingThermalPrintTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Walkin Customer",
            phone="9876543210",
            whatsapp_no="9876543210",
            address="Main Road, Pune",
        )
        self.order = Order.objects.create(
            customer=self.customer,
            customer_name="Walkin Customer",
            phone="9876543210",
            shipping_address="Main Road, Pune",
            total_price=Decimal("240.00"),
            subtotal_price=Decimal("240.00"),
            status="Placed",
        )
        self.bill = Bill.objects.create(
            order=self.order,
            recipient_type="ADMIN",
            bill_number="BILL-TEST-001",
            customer_name="Walkin Customer",
            phone="9876543210",
            shipping_address="Main Road, Pune",
            subtotal_amount=Decimal("240.00"),
            total_amount=Decimal("240.00"),
        )
        BillItem.objects.create(
            bill=self.bill,
            product_name="Test Bread",
            quantity=2,
            unit_price=Decimal("120.00"),
        )

    @staticmethod
    def _create_dashboard_user(username, email, is_superuser):
        return User.objects.create_user(
            username=username,
            email=email,
            password="SecurePass12345",
            is_staff=True,
            is_superuser=is_superuser,
        )

    def test_thermal_print_page_is_accessible_for_staff(self):
        staff_user = self._create_dashboard_user("staffone", "staffone@example.com", False)
        self.client.force_login(staff_user)
        response = self.client.get(reverse("admin-bill-thermal-print", kwargs={"bill_id": self.bill.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.bill.bill_number)
        self.assertContains(response, "Thermal Receipt (3-inch)")

    def test_thermal_print_page_is_accessible_for_admin(self):
        admin_user = self._create_dashboard_user("adminone", "adminone@example.com", True)
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin-bill-thermal-print", kwargs={"bill_id": self.bill.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thathwamasi Bakery Cafe")

    def test_thermal_print_requires_staff_session(self):
        basic_user = User.objects.create_user(
            username="basicuser",
            email="basic@example.com",
            password="SecurePass12345",
            is_staff=False,
            is_superuser=False,
        )
        self.client.force_login(basic_user)
        response = self.client.get(reverse("admin-bill-thermal-print", kwargs={"bill_id": self.bill.id}))
        self.assertEqual(response.status_code, 403)

    def test_bill_detail_and_list_include_thermal_print_links(self):
        admin_user = self._create_dashboard_user("admintwo", "admintwo@example.com", True)
        self.client.force_login(admin_user)

        detail = self.client.get(reverse("admin-bill-detail", kwargs={"bill_id": self.bill.id}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, reverse("admin-bill-thermal-print", kwargs={"bill_id": self.bill.id}))

        listing = self.client.get(reverse("admin-billing-list"))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, reverse("admin-bill-thermal-print", kwargs={"bill_id": self.bill.id}))
