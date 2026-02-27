from django.urls import path

from .views import (
    NotificationFeedAPIView,
    NotificationMarkAllReadAPIView,
    NotificationMarkReadAPIView,
    NotificationUnreadCountAPIView,
)

urlpatterns = [
    path("feed/", NotificationFeedAPIView.as_view(), name="notification-feed"),
    path("unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),
    path("mark-read/", NotificationMarkReadAPIView.as_view(), name="notification-mark-read"),
    path("mark-all-read/", NotificationMarkAllReadAPIView.as_view(), name="notification-mark-all-read"),
]
