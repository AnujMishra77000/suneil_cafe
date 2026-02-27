from django.urls import path
from .views import (
    SectionListAPIView,
    CategoryBySectionAPIView,
    ProductByCategoryAPIView,
    ProductBySectionAPIView,
    ProductDetailAPIView,
    ProductSearchAPIView,
    ProductViewLogCreateAPIView,
    RelatedProductAPIView,
    CategoryCardAPIView,
)

urlpatterns = [

    # 🧁 1. List Sections (Bakery / Snacks)
    path('sections/', SectionListAPIView.as_view(), name='section-list'),

    # 🍞 2. Categories under a Section
    # Example: /api/products/sections/1/categories/
    path('sections/<int:section_id>/categories/', CategoryBySectionAPIView.as_view(), name='category-by-section'),
    path('category-cards/', CategoryCardAPIView.as_view(), name='category-cards'),

    # Products under a Section (across categories)
    path('sections/<int:section_id>/products/', ProductBySectionAPIView.as_view(), name='products-by-section'),

    # 🍩 3. Products under a Category
    # Example: /api/products/categories/5/products/
    path('categories/<int:category_id>/products/', ProductByCategoryAPIView.as_view(), name='products-by-category'),

    # 🧁 4. Single Product Details
    # Example: /api/products/10/
    path('<int:pk>/', ProductDetailAPIView.as_view(), name='product-detail'),
    path('<int:pk>/related/', RelatedProductAPIView.as_view(), name='product-related'),

    # 🔍 5. Search Products
    # Example: /api/products/search/?q=cake
    path('search/', ProductSearchAPIView.as_view(), name='product-search'),
    path('view-log/', ProductViewLogCreateAPIView.as_view(), name='product-view-log'),
]
