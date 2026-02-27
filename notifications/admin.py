from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "recipient_type",
        "recipient_identifier",
        "event_type",
        "is_read",
        "created_at",
    )
    search_fields = (
        "recipient_identifier",
        "title",
        "message",
        "order__phone",
        "order__customer_name",
    )
    list_filter = ("recipient_type", "event_type", "is_read", "created_at")
    ordering = ("-created_at",)
