from django.db.models import Q
from django.contrib.postgres.search import SearchQuery, SearchRank
from .models import Category, Product


class ProductRepository:
    @staticmethod
    def admin_categories_by_section(section_id):
        return Category.objects.filter(section_id=section_id).only("id", "name").order_by("name")

    @staticmethod
    def admin_related_products_by_section(section_id, limit=200):
        return (
            Product.objects.filter(category__section_id=section_id)
            .only("id", "name", "created_at")
            .order_by("-created_at", "name")[:limit]
        )

    @staticmethod
    def category_cards(section):
        section_key = (section or "").strip().lower()
        if section_key in {"snack", "snacks"}:
            category_filter = Q(section__name__in=["Snacks", "Snack"])
            product_section_filter = Q(category__section__name__in=["Snacks", "Snack"])
        elif section_key in {"bakery", "backery"}:
            category_filter = Q(section__name__in=["Bakery", "Backery"])
            product_section_filter = Q(category__section__name__in=["Bakery", "Backery"])
        else:
            category_filter = Q(section__name__icontains=section)
            product_section_filter = Q(category__section__name__icontains=section)

        categories = (
            Category.objects.select_related("section")
            .filter(category_filter)
            .order_by("name")
        )
        data = [
            {
                "id": category.id,
                "name": category.name,
                "section": category.section.name,
            }
            for category in categories
        ]

        if data:
            return data

        # Fallback: derive category cards from product table when category
        # records are inconsistent or section mapping has spelling variants.
        rows = (
            Product.objects.select_related("category", "category__section")
            .filter(product_section_filter)
            .values("category_id", "category__name", "category__section__name")
            .distinct()
            .order_by("category__name")
        )
        return [
            {
                "id": row["category_id"],
                "name": row["category__name"],
                "section": row["category__section__name"],
            }
            for row in rows
        ]

    @staticmethod
    def by_category(category_id):
        return (
            Product.objects.select_related("category", "category__section")
            .only(
                "id",
                "name",
                "description",
                "price",
                "stock_qty",
                "is_available",
                "image",
                "category__id",
                "category__name",
                "category__section__name",
            )
            .filter(category_id=category_id)
            .order_by("-created_at", "name")
        )

    @staticmethod
    def by_section(section_id):
        return (
            Product.objects.select_related("category", "category__section")
            .only(
                "id",
                "name",
                "description",
                "price",
                "stock_qty",
                "is_available",
                "image",
                "category__id",
                "category__name",
                "category__section__name",
            )
            .filter(category__section_id=section_id)
            .order_by("-created_at", "name")
        )

    @staticmethod
    def search(query):
        search_query = SearchQuery(query)
        products = (
            Product.objects.select_related("category", "category__section")
            .annotate(rank=SearchRank("search_vector", search_query))
            .filter(rank__gte=0.05)
            .order_by("-rank", "name")
        )
        if products.exists():
            return products

        return (
            Product.objects.select_related("category", "category__section")
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(category__section__name__icontains=query)
            )
            .distinct()
            .order_by("name")
        )
