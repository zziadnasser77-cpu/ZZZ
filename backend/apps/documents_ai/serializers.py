from rest_framework import serializers

from apps.documents_ai.models import Document, ExtractionField, ExtractionJob


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "document_number",
            "title",
            "document_type",
            "file",
            "file_size",
            "file_hash",
            "content_type",
            "language",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "document_number",
            "file_size",
            "file_hash",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        validated_data["uploaded_by"] = self.context["request"].user
        f = validated_data.get("file")
        if f:
            validated_data["file_size"] = getattr(f, "size", 0)
            validated_data["content_type"] = getattr(f, "content_type", "")
        return super().create(validated_data)


class ExtractionFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractionField
        fields = [
            "id",
            "job",
            "field_key",
            "extracted_value",
            "corrected_value",
            "page_number",
            "confidence",
            "is_approved",
            "is_unknown_or_missing",
            "created_at",
        ]
        read_only_fields = ["id", "job", "created_at"]


class ExtractionJobSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)
    document_number = serializers.CharField(source="document.document_number", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.full_name", read_only=True)
    fields = ExtractionFieldSerializer(many=True, read_only=True)

    class Meta:
        model = ExtractionJob
        fields = [
            "id",
            "job_number",
            "document",
            "document_title",
            "document_number",
            "target_entity_type",
            "status",
            "provider",
            "confidence_score",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_notes",
            "fields",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "job_number",
            "confidence_score",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
