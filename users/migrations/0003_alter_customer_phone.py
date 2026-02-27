from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_customer_address"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="phone",
            field=models.CharField(db_index=True, max_length=15),
        ),
    ]
