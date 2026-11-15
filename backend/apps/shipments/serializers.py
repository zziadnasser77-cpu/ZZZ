from rest_framework import serializers

from apps.common.serializers import CostRestrictedMixin

from .models import Shipment, ShipmentDocument, ShipmentEvent


class ShipmentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentDocument
        fields = [
            "id",
            "shipment",
            "doc_type",
            "document_number",
            "file_url",
            "issue_date",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ShipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = ["id", "shipment", "location_name", "event_description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ShipmentSerializer(CostRestrictedMixin, serializers.ModelSerializer):
    cost_fields = ('freight_cost', 'customs_cost')
    supplier_order_number = serializers.CharField(
        source="supplier_order.order_number", read_only=True, default=None
    )
    sales_order_number = serializers.CharField(
        source="sales_order.order_number", read_only=True, default=None
    )
    documents = ShipmentDocumentSerializer(many=True, read_only=True)
    events = ShipmentEventSerializer(many=True, read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id",
            "shipment_number",
            "supplier_order",
            "supplier_order_number",
            "sales_order",
            "sales_order_number",
            "carrier_name",
            "tracking_number",
            "shipping_method",
            "status",
            "origin_port",
            "destination_port",
            "estimated_departure",
            "actual_departure",
            "estimated_arrival",
            "actual_arrival",
            "freight_cost",
            "customs_cost",
            "notes",
            "documents",
            "events",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "shipment_number", "created_at", "updated_at"]
