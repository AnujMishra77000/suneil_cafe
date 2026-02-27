from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import (
    NotificationFeedQuerySerializer,
    NotificationMarkReadSerializer,
    NotificationRecipientSerializer,
    NotificationSerializer,
)
from .services import get_admin_identifier


class PublicAPIView(APIView):
    permission_classes = [permissions.AllowAny]


class NotificationRecipientMixin:
    def resolve_recipient_scope(self, request, serializer):
        recipient_type = serializer.validated_data["recipient_type"]
        recipient_identifier = serializer.validated_data.get("recipient_identifier", "")

        if recipient_type == Notification.RecipientType.ADMIN:
            if not bool(getattr(request.user, "is_staff", False)):
                raise PermissionDenied("Admin notifications require admin login")
            recipient_identifier = recipient_identifier or get_admin_identifier()

        if recipient_type == Notification.RecipientType.USER and not recipient_identifier:
            raise ValidationError({"recipient_identifier": "Phone is required for user notifications"})

        return recipient_type, recipient_identifier


class NotificationFeedAPIView(NotificationRecipientMixin, PublicAPIView):
    def get(self, request):
        query_serializer = NotificationFeedQuerySerializer(data=request.GET)
        query_serializer.is_valid(raise_exception=True)

        recipient_type, recipient_identifier = self.resolve_recipient_scope(request, query_serializer)
        limit = query_serializer.validated_data["limit"]
        since_id = query_serializer.validated_data.get("since_id")

        # `select_related("order")` avoids per-notification FK fetches in serializer.
        qs = Notification.objects.select_related("order").filter(
            recipient_type=recipient_type,
            recipient_identifier=recipient_identifier,
        ).order_by("-created_at", "-id")

        if since_id:
            qs = qs.filter(id__gt=since_id)

        notifications = list(qs[:limit])
        unread_count = Notification.objects.filter(
            recipient_type=recipient_type,
            recipient_identifier=recipient_identifier,
            is_read=False,
        ).count()

        latest_id = notifications[0].id if notifications else None

        return Response(
            {
                "notifications": NotificationSerializer(notifications, many=True).data,
                "unread_count": unread_count,
                "latest_id": latest_id,
            }
        )


class NotificationUnreadCountAPIView(NotificationRecipientMixin, PublicAPIView):
    def get(self, request):
        query_serializer = NotificationRecipientSerializer(data=request.GET)
        query_serializer.is_valid(raise_exception=True)

        recipient_type, recipient_identifier = self.resolve_recipient_scope(request, query_serializer)

        qs = Notification.objects.filter(
            recipient_type=recipient_type,
            recipient_identifier=recipient_identifier,
        )
        unread_count = qs.filter(is_read=False).count()
        latest_id = qs.order_by("-id").values_list("id", flat=True).first()

        return Response({"unread_count": unread_count, "latest_id": latest_id})


class NotificationMarkReadAPIView(NotificationRecipientMixin, PublicAPIView):
    def post(self, request):
        serializer = NotificationMarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient_type, recipient_identifier = self.resolve_recipient_scope(request, serializer)
        notification_ids = serializer.validated_data["notification_ids"]

        updated = Notification.objects.filter(
            recipient_type=recipient_type,
            recipient_identifier=recipient_identifier,
            id__in=notification_ids,
            is_read=False,
        ).update(
            is_read=True,
            status=Notification.StatusChoices.READ,
        )

        unread_count = Notification.objects.filter(
            recipient_type=recipient_type,
            recipient_identifier=recipient_identifier,
            is_read=False,
        ).count()

        return Response({"updated": updated, "unread_count": unread_count}, status=status.HTTP_200_OK)


class NotificationMarkAllReadAPIView(NotificationRecipientMixin, PublicAPIView):
    def post(self, request):
        serializer = NotificationRecipientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient_type, recipient_identifier = self.resolve_recipient_scope(request, serializer)

        updated = Notification.objects.filter(
            recipient_type=recipient_type,
            recipient_identifier=recipient_identifier,
            is_read=False,
        ).update(
            is_read=True,
            status=Notification.StatusChoices.READ,
        )

        return Response({"updated": updated, "unread_count": 0}, status=status.HTTP_200_OK)
