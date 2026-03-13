from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0014_dashboardaccountprofile_display_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BillPrintJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("CLAIMED", "Claimed"),
                            ("PRINTED", "Printed"),
                            ("FAILED", "Failed"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=12,
                    ),
                ),
                ("agent_id", models.CharField(blank=True, db_index=True, default="", max_length=120)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("claimed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "bill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="print_jobs",
                        to="orders.bill",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bill_print_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="ord_bp_status_created_idx"),
                    models.Index(fields=["bill", "status"], name="ord_bp_bill_status_idx"),
                    models.Index(fields=["agent_id", "claimed_at"], name="ord_bp_agent_claimed_idx"),
                ],
            },
        ),
    ]
