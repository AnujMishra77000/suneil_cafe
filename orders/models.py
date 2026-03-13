from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
import re

from products.models import Product
from users.models import Customer

from .coupon_rules import extract_discount_percent, normalize_coupon_code


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_index=True)
    customer_name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="", db_index=True)
    shipping_address = models.TextField(blank=True, default="")
    idempotency_key = models.UUIDField(default=None, null=True, blank=True, unique=True, db_index=True)
    subtotal_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=64, blank=True, default="", db_index=True)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, default="Placed", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["customer", "created_at"]),
            models.Index(fields=["phone", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["coupon_code", "created_at"]),
        ]

    def __str__(self):
        return f"Order {self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_index=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="orders_unique_item_per_product"),
        ]
        indexes = [
            models.Index(fields=["product"]),
        ]


class OrderFeedback(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="feedback")
    phone = models.CharField(max_length=20)
    rating = models.PositiveSmallIntegerField(blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
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

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_attempt_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} - {self.status}"


class Bill(models.Model):
    RECIPIENT_TYPE = (
        ("USER", "User"),
        ("ADMIN", "Admin"),
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="bills", db_index=True)
    recipient_type = models.CharField(max_length=10, choices=RECIPIENT_TYPE)
    bill_number = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, db_index=True)
    shipping_address = models.TextField(blank=True, default="")
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=64, blank=True, default="", db_index=True)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("order", "recipient_type")
        indexes = [
            models.Index(fields=["recipient_type", "created_at"]),
            models.Index(fields=["phone", "created_at"]),
            models.Index(fields=["coupon_code", "created_at"]),
        ]

    def __str__(self):
        return f"{self.bill_number}"


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="items", db_index=True)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)


class BillPrintJob(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_CLAIMED = "CLAIMED"
    STATUS_PRINTED = "PRINTED"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_CLAIMED, "Claimed"),
        (STATUS_PRINTED, "Printed"),
        (STATUS_FAILED, "Failed"),
    )

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="print_jobs", db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bill_print_jobs",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    agent_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    claimed_at = models.DateTimeField(blank=True, null=True, db_index=True)
    completed_at = models.DateTimeField(blank=True, null=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["bill", "status"]),
            models.Index(fields=["agent_id", "claimed_at"]),
        ]

    def __str__(self):
        return f"PrintJob #{self.id} | Bill {self.bill_id} | {self.status}"


class SalesRecord(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="sales_records", db_index=True)
    category = models.CharField(max_length=120)
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    sold_at = models.DateTimeField(auto_now_add=True, db_index=True)

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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
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


class DeliveryContactSetting(models.Model):
    delivery_contact_number = models.CharField(max_length=15, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery contact setting"
        verbose_name_plural = "Delivery contact setting"

    def clean(self):
        normalized = "".join(ch for ch in str(self.delivery_contact_number or "") if ch.isdigit())
        if normalized and len(normalized) != 10:
            raise ValidationError({"delivery_contact_number": "Delivery contact number must be exactly 10 digits"})
        self.delivery_contact_number = normalized

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.delivery_contact_number or "No delivery contact"


class CouponCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["is_active", "code"]),
        ]

    @property
    def discount_percent(self):
        return extract_discount_percent(self.code)

    def clean(self):
        self.code = normalize_coupon_code(self.code)
        extract_discount_percent(self.code)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        state = "Active" if self.is_active else "Inactive"
        return f"{self.code} ({self.discount_percent}% - {state})"


class DashboardAccountProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dashboard_profile")
    display_name = models.CharField(max_length=150, blank=True, default="")
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def clean(self):
        self.display_name = " ".join(str(self.display_name or "").strip().split())
        if self.display_name and not re.fullmatch(r"[A-Za-z ]+", self.display_name):
            raise ValidationError({"display_name": "Display name can contain only letters and spaces"})
        self.email = (self.email or "").strip().lower()
        digits = "".join(ch for ch in str(self.mobile_number or "") if ch.isdigit())
        if len(digits) != 10:
            raise ValidationError({"mobile_number": "Mobile number must be exactly 10 digits"})
        self.mobile_number = digits

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_name or self.user.username} ({self.email})"


class DashboardLoginActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_login_activities",
    )
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15, blank=True, default="")
    session_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    login_at = models.DateTimeField(auto_now_add=True, db_index=True)
    logout_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ["-login_at"]
        indexes = [
            models.Index(fields=["user", "login_at"]),
            models.Index(fields=["logout_at", "login_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.login_at:%Y-%m-%d %H:%M:%S}"
