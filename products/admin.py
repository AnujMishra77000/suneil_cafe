from django.contrib import admin
from .models import Advertisement, Section, Category, Product

admin.site.register(Section)
admin.site.register(Category)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price", "stock_qty", "is_available", "created_at")
    list_filter = ("is_available", "category__section", "category")
    search_fields = ("name", "description", "category__name", "category__section__name")
    ordering = ("-created_at",)
    list_editable = ("stock_qty",)
    readonly_fields = ("created_at",)
    filter_horizontal = ("related_products",)


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "display_order", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "subtitle")
    ordering = ("display_order", "-created_at")
