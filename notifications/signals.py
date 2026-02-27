from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from orders.models import Order

from .models import Notification
from .services import create_order_notifications


def _is_confirmed(status_value):
    return "confirm" in str(status_value or "").strip().lower()


@receiver(pre_save, sender=Order)
def _capture_previous_order_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status_for_notifications = ""
        return
    instance._previous_status_for_notifications = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first() or ""
    )


@receiver(post_save, sender=Order)
def _create_order_confirmed_notifications(sender, instance, created, **kwargs):
    if created:
        return

    prev_status = getattr(instance, "_previous_status_for_notifications", "")
    current_status = instance.status

    if not _is_confirmed(prev_status) and _is_confirmed(current_status):
        create_order_notifications(
            order=instance,
            event_type=Notification.EventType.ORDER_CONFIRMED,
        )
