from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.coupon_catalog import DEFAULT_COUPON_CODES
from orders.models import CouponCode, DashboardAccountProfile


User = get_user_model()


class CouponManagerTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="couponadmin",
            email="couponadmin@example.com",
            password="AdminPass12345",
            is_staff=True,
            is_superuser=True,
        )
        DashboardAccountProfile.objects.create(
            user=self.admin_user,
            email="couponadmin@example.com",
            mobile_number="9044444444",
        )
        self.client.force_login(self.admin_user)

    def test_coupon_manager_preloads_default_coupon_catalog(self):
        response = self.client.get(reverse("admin-coupon-manage"))
        self.assertEqual(response.status_code, 200)

        codes_in_db = set(CouponCode.objects.values_list("code", flat=True))
        self.assertTrue(set(DEFAULT_COUPON_CODES).issubset(codes_in_db))
        self.assertContains(response, "SPCL10")
        self.assertContains(response, "DWLI30")
        self.assertContains(response, "NEY25")

    def test_coupon_manager_bulk_activation_updates_selected_coupons(self):
        self.client.get(reverse("admin-coupon-manage"))
        response = self.client.post(
            reverse("admin-coupon-manage"),
            {
                "action": "bulk_set",
                "active_codes": ["SPCL10", "RMC20", "DWLI30"],
            },
        )
        self.assertEqual(response.status_code, 302)

        self.assertTrue(CouponCode.objects.get(code="SPCL10").is_active)
        self.assertTrue(CouponCode.objects.get(code="RMC20").is_active)
        self.assertTrue(CouponCode.objects.get(code="DWLI30").is_active)
        self.assertFalse(CouponCode.objects.get(code="SPCL15").is_active)
        self.assertFalse(CouponCode.objects.get(code="RMC10").is_active)

