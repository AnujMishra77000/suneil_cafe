from django.db import models


class Notification(models.Model):
    class RecipientType(models.TextChoices):
        USER = "USER", "User"
        ADMIN = "ADMIN", "Admin"

    class StatusChoices(models.TextChoices):
        CREATED = "CREATED", "Created"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        READ = "READ", "Read"

    class EventType(models.TextChoices):
        ORDER_PLACED = "ORDER_PLACED", "Order Placed"
        ORDER_CONFIRMED = "ORDER_CONFIRMED", "Order Confirmed"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, db_index=True)
    recipient_type = models.CharField(
        max_length=10,
        choices=RecipientType.choices,
        db_index=True,
    )
    recipient_identifier = models.CharField(max_length=100, db_index=True)
    event_type = models.CharField(
        max_length=32,
        choices=EventType.choices,
        default=EventType.ORDER_PLACED,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.CREATED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "event_type", "recipient_type", "recipient_identifier"],
                name="notifications_unique_event_recipient_per_order",
            )
        ]
        indexes = [
            models.Index(fields=["recipient_type", "recipient_identifier", "is_read", "created_at"]),
            models.Index(fields=["recipient_type", "recipient_identifier", "id"]),
            models.Index(fields=["order", "event_type", "recipient_type"]),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.recipient_type} - Order {self.order_id} - {self.event_type}"
