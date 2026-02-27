from django.core.cache import cache
from .repositories import ProductRepository


class ProductService:
    @staticmethod
    def category_cards(section):
        section_key = (section or "").strip().lower()
        cache_key = f"products:category_cards:v5:{section_key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        data = ProductRepository.category_cards(section)
        # Avoid long-lived blank caches.
        cache.set(cache_key, data, 120 if not data else 600)
        return data

    @staticmethod
    def products_by_category(category_id):
        return ProductRepository.by_category(category_id)

    @staticmethod
    def products_by_section(section_id):
        return ProductRepository.by_section(section_id)

    @staticmethod
    def search(query):
        return ProductRepository.search(query)

    @staticmethod
    def admin_form_options(section_id, load_related=False):
        categories = ProductRepository.admin_categories_by_section(section_id)
        related = []
        if load_related:
            cache_key = f"products:admin_related:v1:{section_id}"
            cached = cache.get(cache_key)
            if cached is not None:
                related = cached
            else:
                related_qs = ProductRepository.admin_related_products_by_section(section_id)
                related = [(p.id, p.name) for p in related_qs]
                cache.set(cache_key, related, 300)
        return {
            "categories": categories,
            "related": related,
        }
