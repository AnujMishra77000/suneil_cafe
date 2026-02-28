"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.system_views import ArchitectureStatusAPIView
from orders.views import (
    AdminDashboardView,
    AdminPincodeManageView,
    AdminOrderDetailsView,
    AdminBillingListView,
    AdminBillDetailView,
    AdminBillEditView,
    AdminSalesAnalyticsView,
    AdminCategorySalesDetailView,
    AdminSalesVisualizationSelectorView,
    AdminSalesVisualizationDetailView,
    AdminSalesVisualizationChartImageView,
)
from products.views import (
    StorefrontHomeView,
    StorefrontSectionView,
    StorefrontCategoryView,
    BillingPageView,
    CustomerOrderDetailsPageView,
    CheckoutPageView,
    BuyProductPageView,
    LatencyDashboardView,
    AdminProductSectionSelectView,
    AdminProductCreateView,
    AdminAdvertisingManageView,
    AdminStockTrackerView,
    AdminStockListAPIView,
    AdminStockUpdateAPIView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', StorefrontHomeView.as_view(), name='storefront-home'),
    path('billing/', BillingPageView.as_view(), name='billing-page'),
    path('order-details/', CustomerOrderDetailsPageView.as_view(), name='customer-order-details'),
    path('checkout/', CheckoutPageView.as_view(), name='checkout-page'),
    path('buy/<int:product_id>/', BuyProductPageView.as_view(), name='buy-product-page'),
    path('latency-dashboard/', LatencyDashboardView.as_view(), name='latency-dashboard'),
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin-dashboard/order-details/', AdminOrderDetailsView.as_view(), name='admin-order-details'),
    path('admin-dashboard/pincodes/', AdminPincodeManageView.as_view(), name='admin-pincode-manage'),
    path('admin-dashboard/billing/', AdminBillingListView.as_view(), name='admin-billing-list'),
    path('admin-dashboard/billing/<int:bill_id>/', AdminBillDetailView.as_view(), name='admin-bill-detail'),
    path('admin-dashboard/billing/<int:bill_id>/edit/', AdminBillEditView.as_view(), name='admin-bill-edit'),
    path(
        'admin-dashboard/products/add/',
        AdminProductSectionSelectView.as_view(),
        name='admin-product-section-select'
    ),
    path(
        'admin-dashboard/products/add/<int:section_id>/',
        AdminProductCreateView.as_view(),
        name='admin-product-add'
    ),
    path(
        'admin-dashboard/stock/',
        AdminStockTrackerView.as_view(),
        name='admin-stock-tracker'
    ),
    path(
        'admin-dashboard/advertising/',
        AdminAdvertisingManageView.as_view(),
        name='admin-advertising-manage'
    ),
    path('admin-dashboard/analytics/', AdminSalesAnalyticsView.as_view(), name='admin-sales-analytics'),
    path(
        'admin-dashboard/analytics/visualization/',
        AdminSalesVisualizationSelectorView.as_view(),
        name='admin-sales-visualization-selector'
    ),
    path(
        'admin-dashboard/analytics/visualization/<str:section_slug>/',
        AdminSalesVisualizationDetailView.as_view(),
        name='admin-sales-visualization-detail'
    ),
    path(
        'admin-dashboard/analytics/visualization/<str:section_slug>/chart.png',
        AdminSalesVisualizationChartImageView.as_view(),
        name='admin-sales-visualization-chart'
    ),
    path(
        'admin-dashboard/analytics/category/<int:category_id>/',
        AdminCategorySalesDetailView.as_view(),
        name='admin-category-sales-detail'
    ),
    path('api/products/', include('products.urls')),
    path('api/products/admin/stock/', AdminStockListAPIView.as_view(), name='admin-stock-list-api'),
    path('api/products/admin/stock/update/', AdminStockUpdateAPIView.as_view(), name='admin-stock-update-api'),
    path('api/cart/', include('cart.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/system/architecture/', ArchitectureStatusAPIView.as_view(), name='system-architecture-status'),
    path(
        'backery/category/<int:category_id>/',
        StorefrontCategoryView.as_view(),
        {'section_name': 'bakery'},
        name='storefront-backery-category'
    ),
    path('<str:section_name>/category/<int:category_id>/', StorefrontCategoryView.as_view(), name='storefront-category'),
    path('backery/', StorefrontSectionView.as_view(), {'section_name': 'bakery'}, name='storefront-backery'),
    path('<str:section_name>/', StorefrontSectionView.as_view(), name='storefront-section'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
