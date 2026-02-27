from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_bill_billitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="bill",
            name="shipping_address",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_name",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="order",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_address",
            field=models.TextField(blank=True, default=""),
        ),
    ]
