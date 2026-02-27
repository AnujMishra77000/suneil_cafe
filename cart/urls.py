from django.urls import path
from .views import (
    AddToCartAPIView,
    ViewCartAPIView,
    PlaceOrderAPIView,
    UpdateCartItemAPIView,
    RemoveCartItemAPIView,
    CartCacheDebugAPIView,
)

urlpatterns = [
    path('add/', AddToCartAPIView.as_view()),
    path('view/', ViewCartAPIView.as_view()),
    path('item/update/', UpdateCartItemAPIView.as_view()),
    path('item/remove/', RemoveCartItemAPIView.as_view()),
    path('place/', PlaceOrderAPIView.as_view()),
    path('debug/cache/', CartCacheDebugAPIView.as_view()),
]
