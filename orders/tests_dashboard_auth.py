from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import DashboardAccountProfile


User = get_user_model()


@override_settings(ADMIN_MASTER_PASSWORD="MasterPass123")
class DashboardAuthTests(TestCase):
    def test_dashboard_portal_shows_navigation_cards(self):
        response = self.client.get(reverse("dashboard-auth-portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Registration")
        self.assertContains(response, reverse("dashboard-auth-admin-register"))
        self.assertContains(response, reverse("dashboard-auth-admin-login"))
        self.assertContains(response, reverse("dashboard-auth-staff-login"))
        self.assertNotContains(response, reverse("dashboard-auth-staff-register"))

    def test_admin_registration_creates_admin_profile(self):
        response = self.client.post(
            reverse("dashboard-auth-admin-register"),
            {
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

    def test_staff_registration_requires_admin_login(self):
        response = self.client.get(reverse("dashboard-auth-staff-register"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard-auth-admin-login"), response["Location"])
        self.assertIn("blocked=staff-register", response["Location"])

    def test_staff_registration_creates_staff_profile(self):
        admin_user = User.objects.create_user(
            username="boss",
            email="boss@example.com",
            password="BossPass12345",
            is_staff=True,
            is_superuser=True,
        )
        DashboardAccountProfile.objects.create(user=admin_user, email="boss@example.com", mobile_number="9998887776")
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("dashboard-auth-staff-register"),
            {
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
            reverse("dashboard-auth-admin-login"),
            {
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
            reverse("dashboard-auth-staff-login"),
            {
                "staff_login-email": "boss@example.com",
                "staff_login-password": "BossPass12345",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "not registered as a Staff account", status_code=400)

    def test_admin_login_page_does_not_show_staff_registration_card(self):
        response = self.client.get(reverse("dashboard-auth-admin-login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Open Staff Registration")

    def test_staff_registration_card_visible_only_to_admin_on_dashboard(self):
        admin_user = User.objects.create_user(
            username="chiefadmin",
            email="chiefadmin@example.com",
            password="ChiefPass12345",
            is_staff=True,
            is_superuser=True,
        )
        DashboardAccountProfile.objects.create(
            user=admin_user,
            email="chiefadmin@example.com",
            mobile_number="9011111111",
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("dashboard-auth-staff-register"))

        self.client.logout()

        staff_user = User.objects.create_user(
            username="floorstaff02",
            email="floorstaff02@example.com",
            password="StaffPass12345",
            is_staff=True,
            is_superuser=False,
        )
        DashboardAccountProfile.objects.create(
            user=staff_user,
            email="floorstaff02@example.com",
            mobile_number="9022222222",
        )
        self.client.force_login(staff_user)
        response = self.client.get(reverse("admin-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("dashboard-auth-staff-register"))
