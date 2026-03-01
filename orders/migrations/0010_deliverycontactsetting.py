from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_order_idempotency_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeliveryContactSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("delivery_contact_number", models.CharField(blank=True, default="", max_length=15)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Delivery contact setting",
                "verbose_name_plural": "Delivery contact setting",
            },
        ),
    ]
