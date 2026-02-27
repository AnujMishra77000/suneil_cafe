from django.contrib import admin
from .models import Order, OrderItem, OrderFeedback, Bill, SalesRecord, ServiceablePincode


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "phone", "total_price", "status", "created_at")
    search_fields = ("customer_name", "phone", "shipping_address")
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
    list_display = ("id", "bill_number", "recipient_type", "customer_name", "phone", "total_amount", "created_at")
    search_fields = ("bill_number", "customer_name", "phone", "shipping_address")
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
