from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_couponcode_order_discount_fields_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardLoginActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("mobile_number", models.CharField(blank=True, default="", max_length=15)),
                ("session_key", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("login_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("logout_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_login_activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-login_at"],
                "indexes": [
                    models.Index(fields=["user", "login_at"], name="orders_dash_user_id_050eab_idx"),
                    models.Index(fields=["logout_at", "login_at"], name="orders_dash_logout_111f10_idx"),
                ],
            },
        ),
    ]
