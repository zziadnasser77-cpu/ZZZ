from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation
from apps.identity_access.permissions import HasPermission

from .models import DocumentSequence, OrganizationProfile, validate_sequence_pattern


class OrganizationProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationProfile
        exclude = ["singleton", "created_by", "updated_by"]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrganizationView(APIView):
    permission_classes = [HasPermission]
    permission_map = {
        "get": "settings.organization.view",
        "put": "settings.organization.edit",
        "patch": "settings.organization.edit",
    }

    def get(self, request):
        return Response(OrganizationProfileSerializer(OrganizationProfile.load()).data)

    def patch(self, request):
        obj = OrganizationProfile.load()
        before = OrganizationProfileSerializer(obj).data
        s = OrganizationProfileSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        after = s.data
        diff = {
            k: {"before": before.get(k), "after": after.get(k)}
            for k in after
            if k not in ("updated_at",) and before.get(k) != after.get(k)
        }
        log_event("settings.organization_updated", entity=obj, changes=diff, sensitive=True)
        return Response(after)

    put = patch


class DocumentSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentSequence
        fields = ["id", "doc_type", "year", "branch", "prefix", "pattern", "next_value"]
        read_only_fields = ["doc_type", "year", "branch", "next_value"]

    def validate_pattern(self, value):
        try:
            return validate_sequence_pattern(value)
        except BusinessRuleViolation as exc:
            raise serializers.ValidationError(str(exc.detail)) from exc


class DocumentSequenceViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    queryset = DocumentSequence.objects.order_by("doc_type", "-year")
    serializer_class = DocumentSequenceSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "settings.numbering.view",
        "retrieve": "settings.numbering.view",
        "update": "settings.numbering.edit",
        "partial_update": "settings.numbering.edit",
    }

    def perform_update(self, serializer):
        before = {"prefix": serializer.instance.prefix, "pattern": serializer.instance.pattern}
        seq = serializer.save()
        after = {"prefix": seq.prefix, "pattern": seq.pattern}
        log_event(
            "settings.sequence_updated",
            entity=seq,
            changes={"before": before, "after": after},
            sensitive=True,
        )


router = DefaultRouter()
router.register("document-sequences", DocumentSequenceViewSet, basename="document-sequence")
urlpatterns = router.urls
