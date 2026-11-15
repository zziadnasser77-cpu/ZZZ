from rest_framework import mixins, serializers, viewsets
from rest_framework.routers import DefaultRouter

from apps.identity_access.permissions import HasPermission

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "occurred_at",
            "actor",
            "actor_email",
            "action",
            "entity_type",
            "entity_id",
            "summary",
            "changes",
            "sensitive",
            "ip_address",
            "request_id",
        ]


class AuditEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AuditEvent.objects.select_related("actor")
    serializer_class = AuditEventSerializer
    permission_classes = [HasPermission]
    permission_map = {"list": "audit.event.view", "retrieve": "audit.event.view"}
    filterset_fields = ["action", "entity_type", "entity_id", "actor", "sensitive"]
    search_fields = ["summary", "action"]
    ordering_fields = ["occurred_at"]


router = DefaultRouter()
router.register("audit-events", AuditEventViewSet, basename="audit-event")
urlpatterns = router.urls
