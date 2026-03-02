from decimal import Decimal

from django.db import migrations, models


DEFAULT_COUPONS = ("RESIDENT10", "RMC10")


def seed_coupons_and_backfill(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Bill = apps.get_model("orders", "Bill")
    CouponCode = apps.get_model("orders", "CouponCode")

    for order in Order.objects.all().only("id", "total_price"):
        order.subtotal_price = order.total_price or Decimal("0.00")
        order.discount_amount = Decimal("0.00")
        order.discount_percent = 0
        order.coupon_code = ""
        order.save(update_fields=["subtotal_price", "discount_amount", "discount_percent", "coupon_code"])

    for bill in Bill.objects.all().only("id", "total_amount"):
        bill.subtotal_amount = bill.total_amount or Decimal("0.00")
        bill.discount_amount = Decimal("0.00")
        bill.discount_percent = 0
        bill.coupon_code = ""
        bill.save(update_fields=["subtotal_amount", "discount_amount", "discount_percent", "coupon_code"])

    for code in DEFAULT_COUPONS:
        CouponCode.objects.update_or_create(code=code, defaults={"is_active": True})


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0011_dashboardaccountprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="CouponCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["code"],
                "indexes": [models.Index(fields=["is_active", "code"], name="orders_coup_is_acti_4b7245_idx")],
            },
        ),
        migrations.AddField(
            model_name="bill",
            name="coupon_code",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="bill",
            name="discount_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="bill",
            name="discount_percent",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bill",
            name="subtotal_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="order",
            name="coupon_code",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="order",
            name="discount_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="order",
            name="discount_percent",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="order",
            name="subtotal_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddIndex(
            model_name="bill",
            index=models.Index(fields=["coupon_code", "created_at"], name="orders_bill_coupon__ce4310_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["coupon_code", "created_at"], name="orders_orde_coupon__d426b4_idx"),
        ),
        migrations.RunPython(seed_coupons_and_backfill, migrations.RunPython.noop),
    ]
