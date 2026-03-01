from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


@override_settings(ADMIN_MASTER_PASSWORD="MasterPass123")
class DashboardAuthTests(TestCase):
    def test_admin_bootstrap_creates_first_admin(self):
        response = self.client.post(
            reverse("dashboard-auth-register-admin"),
            {
                "username": "mainadmin",
                "password1": "SecurePass12345",
                "password2": "SecurePass12345",
                "master_password": "MasterPass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="mainadmin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_login_rejects_non_staff_user(self):
        User.objects.create_user(username="customer", password="UserPass12345")
        response = self.client.post(
            reverse("dashboard-auth-login"),
            {"username": "customer", "password": "UserPass12345"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not have dashboard access")

    def test_admin_can_create_staff_credentials(self):
        admin = User.objects.create_superuser("boss", "boss@example.com", "BossPass12345")
        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin-staff-manage"),
            {"full_name": "Floor Staff", "email": "floor@example.com", "role": "staff"},
        )
        self.assertEqual(response.status_code, 200)
        created = User.objects.exclude(username="boss").get()
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertContains(response, created.username)

    def test_admin_can_create_admin_credentials_with_master_password(self):
        admin = User.objects.create_superuser("boss", "boss@example.com", "BossPass12345")
        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin-staff-manage"),
            {
                "full_name": "Ops Admin",
                "email": "ops@example.com",
                "role": "admin",
                "master_password": "MasterPass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        created = User.objects.exclude(username="boss").get()
        self.assertTrue(created.is_staff)
        self.assertTrue(created.is_superuser)
        self.assertContains(response, created.username)
