from django.db import models
from django.core.exceptions import ValidationError
from users.models import Customer
from products.models import Product


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    shipping_address = models.TextField(blank=True, default="")
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, default='Placed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"Order {self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["order", "product"]),
            models.Index(fields=["product"]),
        ]


class OrderFeedback(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="feedback")
    phone = models.CharField(max_length=20)
    rating = models.PositiveSmallIntegerField(blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "updated_at"], name="orders_feed_phone_upd_idx"),
            models.Index(fields=["updated_at"], name="orders_feed_updated_idx"),
        ]

    def clean(self):
        if self.rating is not None and (self.rating < 1 or self.rating > 5):
            raise ValidationError({"rating": "Rating must be between 1 and 5"})
        self.phone = (self.phone or "").strip()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Feedback #{self.order_id}"


class SMSLog(models.Model):
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(max_length=20, default="PENDING")  
    # PENDING / SENT / FAILED

    error_message = models.TextField(blank=True, null=True)
    attempt_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    last_attempt_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} - {self.status}"


class Bill(models.Model):
    RECIPIENT_TYPE = (
        ('USER', 'User'),
        ('ADMIN', 'Admin'),
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='bills')
    recipient_type = models.CharField(max_length=10, choices=RECIPIENT_TYPE)
    bill_number = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    shipping_address = models.TextField(blank=True, default="")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'recipient_type')
        indexes = [
            models.Index(fields=["recipient_type", "created_at"]),
            models.Index(fields=["phone", "created_at"]),
        ]

    def __str__(self):
        return f"{self.bill_number}"


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)


class SalesRecord(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="sales_records")
    category = models.CharField(max_length=120)
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    sold_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["sold_at"]),
            models.Index(fields=["category", "sold_at"]),
            models.Index(fields=["product_name", "sold_at"]),
        ]

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class ServiceablePincode(models.Model):
    code = models.CharField(max_length=6, unique=True)
    area_name = models.CharField(max_length=150, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active", "code"]),
        ]

    def clean(self):
        normalized = "".join(ch for ch in str(self.code or "") if ch.isdigit())
        if len(normalized) != 6:
            raise ValidationError({"code": "Pincode must be exactly 6 digits"})
        self.code = normalized

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} {self.area_name}".strip()
