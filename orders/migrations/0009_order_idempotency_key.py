from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_remove_orderitem_orders_orde_order_i_52f79a_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="idempotency_key",
            field=models.UUIDField(blank=True, db_index=True, default=None, null=True, unique=True),
        ),
    ]
