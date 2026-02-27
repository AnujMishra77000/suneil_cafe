from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "whatsapp_no", "address")
    search_fields = ("name", "phone", "whatsapp_no", "address")
