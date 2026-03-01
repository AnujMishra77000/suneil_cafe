from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import DashboardAccountProfile


User = get_user_model()


@override_settings(ADMIN_MASTER_PASSWORD="MasterPass123")
class DashboardAuthTests(TestCase):
    def test_admin_registration_creates_admin_profile(self):
        response = self.client.post(
            reverse("dashboard-auth-login"),
            {
                "action": "admin_register",
                "admin_register-username": "mainadmin",
                "admin_register-mobile_number": "9876543210",
                "admin_register-email": "admin@example.com",
                "admin_register-password1": "SecurePass12345",
                "admin_register-password2": "SecurePass12345",
                "admin_register-master_password": "MasterPass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="mainadmin")
        profile = DashboardAccountProfile.objects.get(user=user)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(profile.email, "admin@example.com")
        self.assertEqual(profile.mobile_number, "9876543210")

    def test_staff_registration_creates_staff_profile(self):
        response = self.client.post(
            reverse("dashboard-auth-login"),
            {
                "action": "staff_register",
                "staff_register-username": "floorstaff",
                "staff_register-mobile_number": "9123456780",
                "staff_register-email": "staff@example.com",
                "staff_register-password1": "SecurePass12345",
                "staff_register-password2": "SecurePass12345",
                "staff_register-master_password": "MasterPass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="floorstaff")
        profile = DashboardAccountProfile.objects.get(user=user)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(profile.email, "staff@example.com")

    def test_admin_login_uses_email_and_password(self):
        user = User.objects.create_user(
            username="boss",
            email="boss@example.com",
            password="BossPass12345",
            is_staff=True,
            is_superuser=True,
        )
        DashboardAccountProfile.objects.create(user=user, email="boss@example.com", mobile_number="9998887776")
        response = self.client.post(
            reverse("dashboard-auth-login"),
            {
                "action": "admin_login",
                "admin_login-email": "boss@example.com",
                "admin_login-password": "BossPass12345",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_staff_login_rejects_admin_account(self):
        user = User.objects.create_user(
            username="boss",
            email="boss@example.com",
            password="BossPass12345",
            is_staff=True,
            is_superuser=True,
        )
        DashboardAccountProfile.objects.create(user=user, email="boss@example.com", mobile_number="9998887776")
        response = self.client.post(
            reverse("dashboard-auth-login"),
            {
                "action": "staff_login",
                "staff_login-email": "boss@example.com",
                "staff_login-password": "BossPass12345",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "not registered as a Staff account", status_code=400)
