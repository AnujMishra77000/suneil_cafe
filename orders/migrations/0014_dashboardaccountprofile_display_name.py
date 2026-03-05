from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0013_dashboardloginactivity"),
    ]

    operations = [
        migrations.AddField(
            model_name="dashboardaccountprofile",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
