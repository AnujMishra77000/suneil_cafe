from django.conf import settings
from django.core.cache import cache

from .cache_utils import catalog_cache_key
from .repositories import ProductRepository


class ProductService:
    @staticmethod
    def _category_card_image_url(image_value):
        image_value = str(image_value or "").strip()
        if not image_value:
            return ""
        if image_value.startswith(("http://", "https://", "/")):
            return image_value
        media_url = settings.MEDIA_URL or "/media/"
        if not media_url.endswith("/"):
            media_url = f"{media_url}/"
        return f"{media_url}{image_value}"

    @staticmethod
    def category_cards(section):
        section_key = (section or "").strip().lower()
        cache_key = catalog_cache_key("category_cards_v2", section_key)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        data = []
        for item in ProductRepository.category_cards(section):
            payload = dict(item)
            payload["image"] = ProductService._category_card_image_url(payload.get("image"))
            data.append(payload)
        cache.set(cache_key, data, 120 if not data else 300)
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
            cache_key = catalog_cache_key("admin_related", section_id)
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
