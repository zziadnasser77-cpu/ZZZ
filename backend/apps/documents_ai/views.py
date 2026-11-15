from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.documents_ai.models import Document, ExtractionJob
from apps.documents_ai.serializers import DocumentSerializer, ExtractionJobSerializer
from apps.documents_ai.services import (
    review_and_approve_extraction,
    rollback_extraction_approval,
    trigger_ai_extraction,
)
from apps.identity_access.permissions import HasPermission


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related("uploaded_by").all()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [HasPermission]
    permission_map = {
        "list": "documents.document.view",
        "retrieve": "documents.document.view",
        "create": "documents.document.create",
        "update": "documents.document.edit",
        "partial_update": "documents.document.edit",
        "destroy": "documents.document.cancel",
        "trigger_extraction": "documents.extraction.create",
    }
    filterset_fields = ["document_type", "language", "uploaded_by"]
    search_fields = ["document_number", "title"]

    @action(detail=True, methods=["post"])
    def trigger_extraction(self, request, pk=None):
        document = self.get_object()
        target_entity_type = request.data.get(
            "target_entity_type", ExtractionJob.TargetEntityType.PRODUCT_SPECS
        )
        provider = request.data.get("provider", "GEMINI_FLASH_GATEWAY")

        job = trigger_ai_extraction(
            document=document,
            target_entity_type=target_entity_type,
            provider=provider,
            user=request.user,
        )
        return Response(
            ExtractionJobSerializer(job, context={"request": request}).data, status=status.HTTP_201_CREATED
        )


class ExtractionJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        ExtractionJob.objects.select_related("document", "reviewed_by").prefetch_related("fields").all()
    )
    serializer_class = ExtractionJobSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "documents.extraction.view",
        "retrieve": "documents.extraction.view",
        "review": "documents.extraction.approve",
        "rollback": "documents.extraction.approve",
    }
    filterset_fields = ["status", "target_entity_type", "provider", "document"]
    search_fields = ["job_number", "document__title"]

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        job = self.get_object()
        field_corrections = request.data.get("field_corrections", {})
        is_approved = bool(request.data.get("is_approved", True))
        review_notes = request.data.get("review_notes", "")

        reviewed_job = review_and_approve_extraction(
            job=job,
            field_corrections=field_corrections,
            is_approved=is_approved,
            review_notes=review_notes,
            user=request.user,
        )
        return Response(ExtractionJobSerializer(reviewed_job, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def rollback(self, request, pk=None):
        job = self.get_object()
        reason = request.data.get("reason", "طلب تراجع من المستخدم")
        rolled_back = rollback_extraction_approval(job=job, reason=reason, user=request.user)
        return Response(ExtractionJobSerializer(rolled_back, context={"request": request}).data)
