from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.identity_access.permissions import HasPermission
from apps.notifications.models import Notification, NotificationTemplate
from apps.notifications.serializers import (
    NotificationSerializer,
    NotificationTemplateSerializer,
)
from apps.notifications.services import mark_notification_as_read


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["channel", "priority", "status"]
    search_fields = ["title", "message"]

    def get_queryset(self):
        user = self.request.user
        if user.has_perm_code("notifications.notification.manage"):
            return (
                Notification.objects.select_related("recipient").prefetch_related("delivery_attempts").all()
            )
        return (
            Notification.objects.filter(recipient=user)
            .select_related("recipient")
            .prefetch_related("delivery_attempts")
            .all()
        )

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        mark_notification_as_read(notification)
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        qs = Notification.objects.filter(recipient=request.user, status__in=["PENDING", "SENT", "DELIVERED"])
        for n in qs:
            mark_notification_as_read(n)
        return Response({"status": "ok", "marked_count": qs.count()})


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "notifications.template.view",
        "retrieve": "notifications.template.view",
        "create": "notifications.template.create",
        "update": "notifications.template.edit",
        "partial_update": "notifications.template.edit",
        "destroy": "notifications.template.manage",
    }
    filterset_fields = ["channel", "is_active"]
    search_fields = ["code", "name_ar", "name_en"]
