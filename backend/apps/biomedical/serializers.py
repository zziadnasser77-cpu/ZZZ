from rest_framework import serializers

from apps.biomedical.models import (
    InstallationProtocol,
    ServiceTicket,
    ServiceVisit,
    SparePartRequest,
    WarrantyContract,
)
from apps.common.serializers import CostRestrictedMixin


class InstallationProtocolSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    asset_serial = serializers.CharField(source="asset.serial_number", read_only=True)
    model_name = serializers.CharField(source="asset.model.model_name", read_only=True)
    lead_engineer_name = serializers.CharField(source="lead_engineer.full_name", read_only=True)

    class Meta:
        model = InstallationProtocol
        fields = [
            "id",
            "protocol_number",
            "asset",
            "asset_serial",
            "model_name",
            "customer",
            "customer_name",
            "location",
            "installed_at",
            "lead_engineer",
            "lead_engineer_name",
            "status",
            "electrical_safety_passed",
            "performance_verification_passed",
            "user_training_completed",
            "trainees_list",
            "customer_representative_name",
            "customer_representative_title",
            "customer_signed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "protocol_number",
            "customer_signed_at",
            "created_at",
            "updated_at",
        ]


class WarrantyContractSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    asset_serial = serializers.CharField(source="asset.serial_number", read_only=True)
    model_name = serializers.CharField(source="asset.model.model_name", read_only=True)

    class Meta:
        model = WarrantyContract
        fields = [
            "id",
            "contract_number",
            "asset",
            "asset_serial",
            "model_name",
            "customer",
            "customer_name",
            "warranty_type",
            "start_date",
            "end_date",
            "sla_response_hours",
            "coverage_details",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "contract_number", "created_at", "updated_at"]


class ServiceVisitSerializer(serializers.ModelSerializer):
    engineer_name = serializers.CharField(source="engineer.full_name", read_only=True)

    class Meta:
        model = ServiceVisit
        fields = [
            "id",
            "ticket",
            "engineer",
            "engineer_name",
            "visit_date",
            "actions_taken",
            "diagnostic_details",
            "is_resolved",
            "customer_sign_off_name",
            "customer_signed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SparePartRequestSerializer(CostRestrictedMixin, serializers.ModelSerializer):
    cost_fields = ('cost_price',)
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True)

    class Meta:
        model = SparePartRequest
        fields = [
            "id",
            "ticket",
            "part_name",
            "part_sku",
            "quantity",
            "coverage",
            "status",
            "cost_price",
            "customer_price",
            "approved_by",
            "approved_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ServiceTicketSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    asset_serial = serializers.CharField(source="asset.serial_number", read_only=True)
    model_name = serializers.CharField(source="asset.model.model_name", read_only=True)
    assigned_engineer_name = serializers.CharField(source="assigned_engineer.full_name", read_only=True)
    visits = ServiceVisitSerializer(many=True, read_only=True)
    spare_parts = SparePartRequestSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceTicket
        fields = [
            "id",
            "ticket_number",
            "ticket_type",
            "priority",
            "asset",
            "asset_serial",
            "model_name",
            "customer",
            "customer_name",
            "assigned_engineer",
            "assigned_engineer_name",
            "title",
            "reported_issue",
            "diagnostic_findings",
            "resolution_summary",
            "warranty_status",
            "status",
            "labor_hours",
            "labor_cost",
            "parts_cost",
            "total_cost",
            "closed_at",
            "created_by",
            "visits",
            "spare_parts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "ticket_number",
            "labor_hours",
            "labor_cost",
            "parts_cost",
            "total_cost",
            "closed_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
