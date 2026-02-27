from datetime import timedelta

from django.core.cache import cache
from django.db.models import Sum, F, Q, Count, DecimalField
from django.db.models.functions import Coalesce
from django.utils.timezone import now

from .models import Order, OrderItem
from products.models import ProductViewLog


ANALYTICS_CACHE_TTL = 60


def sales_summary():
    cache_key = "analytics:sales_summary:v2"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    current_time = now()
    day_start = current_time - timedelta(days=1)
    week_start = current_time - timedelta(days=7)
    month_start = current_time - timedelta(days=30)
    year_start = current_time - timedelta(days=365)

    summary = Order.objects.aggregate(
        daily_sales=Coalesce(
            Sum("total_price", filter=Q(created_at__gte=day_start)),
            0,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        weekly_sales=Coalesce(
            Sum("total_price", filter=Q(created_at__gte=week_start)),
            0,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        monthly_sales=Coalesce(
            Sum("total_price", filter=Q(created_at__gte=month_start)),
            0,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        yearly_sales=Coalesce(
            Sum("total_price", filter=Q(created_at__gte=year_start)),
            0,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )

    cache.set(cache_key, summary, ANALYTICS_CACHE_TTL)
    return summary


def category_sales():
    cache_key = "analytics:category_sales:v2"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = list(
        OrderItem.objects.values(category_name=F("product__category__name"))
        .annotate(
            total_sales=Coalesce(
                Sum(F("price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2)),
                0,
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .order_by("-total_sales")
    )
    cache.set(cache_key, data, ANALYTICS_CACHE_TTL)
    return data


def top_products():
    cache_key = "analytics:top_products:v2"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = list(
        OrderItem.objects.values(name=F("product__name"))
        .annotate(quantity_sold=Coalesce(Sum("quantity"), 0))
        .order_by("-quantity_sold")[:10]
    )
    cache.set(cache_key, data, ANALYTICS_CACHE_TTL)
    return data


def unavailable_product_demand():
    cache_key = "analytics:unavailable_demand:v2"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = list(
        ProductViewLog.objects.values(name=F("product__name"))
        .annotate(views=Count("id"))
        .order_by("-views")
    )
    cache.set(cache_key, data, ANALYTICS_CACHE_TTL)
    return data
