from django.contrib import admin
from .models import (
    Bill,
    BillPrintJob,
    CouponCode,
    DeliveryContactSetting,
    Order,
    OrderFeedback,
    OrderItem,
    SalesRecord,
    ServiceablePincode,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_name",
        "phone",
        "coupon_code",
        "discount_percent",
        "discount_amount",
        "total_price",
        "status",
        "created_at",
    )
    search_fields = ("customer_name", "phone", "shipping_address", "coupon_code")
    list_filter = ("status", "created_at")
    inlines = [OrderItemInline]
    readonly_fields = ("created_at",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "quantity", "price")


@admin.register(OrderFeedback)
class OrderFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "phone", "rating", "updated_at")
    search_fields = ("phone", "order__customer_name", "order__phone", "message")
    list_filter = ("rating", "updated_at")
    ordering = ("-updated_at",)


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bill_number",
        "recipient_type",
        "customer_name",
        "phone",
        "coupon_code",
        "discount_amount",
        "total_amount",
        "created_at",
    )
    search_fields = ("bill_number", "customer_name", "phone", "shipping_address", "coupon_code")
    list_filter = ("recipient_type", "created_at")


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "sold_at", "category", "product_name", "price", "quantity", "order")
    search_fields = ("category", "product_name", "order__customer_name", "order__phone")
    list_filter = ("category", "sold_at")
    ordering = ("-sold_at",)


@admin.register(ServiceablePincode)
class ServiceablePincodeAdmin(admin.ModelAdmin):
    list_display = ("code", "area_name", "is_active", "updated_at")
    search_fields = ("code", "area_name")
    list_filter = ("is_active",)
    ordering = ("code",)


@admin.register(DeliveryContactSetting)
class DeliveryContactSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "delivery_contact_number", "updated_at")
    readonly_fields = ("updated_at",)


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "is_active", "updated_at")
    search_fields = ("code",)
    list_filter = ("is_active",)
    ordering = ("code",)


@admin.register(BillPrintJob)
class BillPrintJobAdmin(admin.ModelAdmin):
    list_display = ("id", "bill", "status", "agent_id", "attempts", "requested_by", "created_at", "completed_at")
    search_fields = ("bill__bill_number", "bill__phone", "agent_id")
    list_filter = ("status", "created_at", "completed_at")
    ordering = ("-created_at",)
