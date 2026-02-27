from django.db import migrations, models


def dedupe_notifications(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    db_alias = schema_editor.connection.alias

    rows = (
        Notification.objects.using(db_alias)
        .order_by("order_id", "event_type", "recipient_type", "recipient_identifier", "id")
        .values_list("id", "order_id", "event_type", "recipient_type", "recipient_identifier")
    )

    seen = set()
    to_delete = []
    for row_id, order_id, event_type, recipient_type, recipient_identifier in rows:
        key = (order_id, event_type, recipient_type, recipient_identifier)
        if key in seen:
            to_delete.append(row_id)
        else:
            seen.add(key)

    if to_delete:
        Notification.objects.using(db_alias).filter(id__in=to_delete).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_alter_notification_created_at_and_more"),
    ]

    operations = [
        migrations.RunPython(dedupe_notifications, noop_reverse),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                fields=("order", "event_type", "recipient_type", "recipient_identifier"),
                name="notifications_unique_event_recipient_per_order",
            ),
        ),
    ]
