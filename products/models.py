from django.db import models
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.contrib.postgres.indexes import GinIndex

# this models is to store section (Bakery/Snacks)
class Section(models.Model): 
    class SectionType(models.TextChoices):
        BAKERY = "Bakery", "Bakery"
        SNACKS = "Snacks", "Snacks"

    name = models.CharField(max_length=100, choices=SectionType.choices, unique=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name

# category of product like Backery -> pav, khari, cacke, butter. Snacks -> dosa, idli, sambhar,medu_wada
class Category(models.Model):
    name = models.CharField(max_length=100)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='categories')

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "section"], name="unique_category_per_section")
        ]
        indexes = [
            models.Index(fields=["section", "name"]),
        ]

    def __str__(self):
        return f"{self.section.name} - {self.name}"
    

# products according to the Category


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_qty = models.PositiveIntegerField(default=20)
    is_available = models.BooleanField(default=True)
    image = models.ImageField(upload_to='products/')
    description = models.TextField(blank=True, null=True)
    search_vector = SearchVectorField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    related_products = models.ManyToManyField("self", blank=True, symmetrical=False)

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector']),
            models.Index(fields=["category", "name"]),
            models.Index(fields=["category", "is_available"]),
            models.Index(fields=["is_available", "created_at"]),
            models.Index(fields=["name"]),
        ]
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.is_available = self.stock_qty > 0
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



class ProductViewLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["product", "viewed_at"]),
        ]

    def __str__(self):
        return f"{self.product.name} unavailable view"


class Advertisement(models.Model):
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=220, blank=True)
    image = models.ImageField(upload_to="ads/")
    cta_label = models.CharField(max_length=40, blank=True, default="")
    cta_url = models.CharField(max_length=500, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "display_order"]),
        ]

    def __str__(self):
        state = "Active" if self.is_active else "Inactive"
        return f"{self.title} ({state})"
