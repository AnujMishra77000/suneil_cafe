from django.db import models

from products.models import Product
from users.models import Customer


class Cart(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Cart of {self.customer.phone}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_index=True)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="cart_unique_product_per_cart"),
        ]
        indexes = [
            models.Index(fields=["product", "cart"]),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
