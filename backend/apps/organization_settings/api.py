from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from apps.audit.services import log_event
from apps.identity_access.permissions import HasPermission

from .models import DocumentSequence, OrganizationProfile


class OrganizationProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationProfile
        exclude = ["singleton", "created_by", "updated_by"]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrganizationView(APIView):
    permission_classes = [HasPermission]
    permission_map = {"get": "settings.organization.view", "put": "settings.organization.edit",
                      "patch": "settings.organization.edit"}

    def get(self, request):
        return Response(OrganizationProfileSerializer(OrganizationProfile.load()).data)

    def patch(self, request):
        obj = OrganizationProfile.load()
        s = OrganizationProfileSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        log_event("settings.organization_updated", entity=obj, changes=request.data, sensitive=True)
        return Response(s.data)

    put = patch


class DocumentSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentSequence
        fields = ["id", "doc_type", "year", "branch", "prefix", "pattern", "next_value"]
        read_only_fields = ["next_value"]


class DocumentSequenceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                              viewsets.GenericViewSet):
    queryset = DocumentSequence.objects.order_by("doc_type", "-year")
    serializer_class = DocumentSequenceSerializer
    permission_classes = [HasPermission]
    permission_map = {"list": "settings.numbering.view", "retrieve": "settings.numbering.view",
                      "update": "settings.numbering.edit", "partial_update": "settings.numbering.edit"}


router = DefaultRouter()
router.register("document-sequences", DocumentSequenceViewSet, basename="document-sequence")
urlpatterns = router.urls
