from django.core.cache import cache
from .admin_repositories import AdminRepository


class AdminAnalyticsService:
    @staticmethod
    def dashboard_payload(range_key):
        rk = range_key if range_key in {"today", "weekly", "monthly", "yearly"} else "today"
        cache_key = f"admin:dashboard:v1:{rk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        payload = {
            "range": rk,
            "summary": AdminRepository.summary(rk),
            "top_products": AdminRepository.top_products(rk),
            "category_sales": AdminRepository.category_sales(rk),
            "growth": AdminRepository.growth_series(rk),
        }
        cache.set(cache_key, payload, 60)
        return payload

    @staticmethod
    def recent_orders_payload(limit=20):
        rows = []
        for order in AdminRepository.recent_orders(limit=limit):
            rows.append(
                {
                    "id": order.id,
                    "customer_name": order.customer_name,
                    "phone": order.phone,
                    "shipping_address": order.shipping_address,
                    "total_price": str(order.total_price),
                    "status": order.status,
                    "created_at": order.created_at,
                    "items": [
                        {
                            "product_name": item.product.name,
                            "quantity": item.quantity,
                            "price": str(item.price),
                        }
                        for item in order.items.all()
                    ],
                }
            )
        return rows
