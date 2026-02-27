from datetime import timedelta
from django.db.models import Sum, F, Count, DecimalField, Q
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from .models import Order, SalesRecord
from products.models import Product


class AdminRepository:
    @staticmethod
    def range_start(range_key):
        now = timezone.now()
        mapping = {
            "today": now - timedelta(days=1),
            "weekly": now - timedelta(days=7),
            "monthly": now - timedelta(days=30),
            "yearly": now - timedelta(days=365),
        }
        return mapping.get(range_key, mapping["today"])

    @staticmethod
    def sales_qs(range_key):
        return SalesRecord.objects.filter(sold_at__gte=AdminRepository.range_start(range_key))

    @staticmethod
    def top_products(range_key):
        return list(
            AdminRepository.sales_qs(range_key)
            .values("product_name")
            .annotate(total_qty=Coalesce(Sum("quantity"), 0))
            .order_by("-total_qty")[:10]
        )

    @staticmethod
    def category_sales(range_key):
        return list(
            AdminRepository.sales_qs(range_key)
            .values("category")
            .annotate(
                total_sales=Coalesce(
                    Sum(F("price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                    0,
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
            .order_by("-total_sales")
        )

    @staticmethod
    def growth_series(range_key):
        return list(
            AdminRepository.sales_qs(range_key)
            .annotate(day=TruncDate("sold_at"))
            .values("day")
            .annotate(
                revenue=Coalesce(
                    Sum(F("price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                    0,
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
                qty=Coalesce(Sum("quantity"), 0),
            )
            .order_by("day")
        )

    @staticmethod
    def summary(range_key):
        qs = AdminRepository.sales_qs(range_key)
        return qs.aggregate(
            total_revenue=Coalesce(
                Sum(F("price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                0,
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            total_quantity=Coalesce(Sum("quantity"), 0),
            total_products=Count("product_name", distinct=True),
        )

    @staticmethod
    def recent_orders(limit=20):
        return Order.objects.prefetch_related("items__product").order_by("-id")[:limit]

    @staticmethod
    def latest_order_id():
        latest = Order.objects.order_by("-id").values_list("id", flat=True).first()
        return latest or 0

    @staticmethod
    def product_search(query):
        q = (query or "").strip()
        return (
            Product.objects.select_related("category", "category__section")
            .filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(category__name__icontains=q)
            )
            .order_by("-created_at", "name")[:30]
        )
