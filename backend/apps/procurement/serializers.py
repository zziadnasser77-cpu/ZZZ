from rest_framework import serializers

from apps.common.serializers import CostRestrictedMixin

from .models import Supplier, SupplierOrder, SupplierOrderLine


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "country",
            "contact_person",
            "email",
            "phone",
            "website",
            "currency",
            "payment_terms",
            "is_primary_partner",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierOrderLineSerializer(CostRestrictedMixin, serializers.ModelSerializer):
    cost_fields = ("unit_cost", "total_cost")
    model_name = serializers.CharField(source="model.model_name", read_only=True)
    sku = serializers.CharField(source="model.sku", read_only=True)

    class Meta:
        model = SupplierOrderLine
        fields = [
            "id",
            "order",
            "model",
            "model_name",
            "sku",
            "description",
            "quantity",
            "unit_cost",
            "total_cost",
            "received_quantity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name_ar", read_only=True)
    deal_number = serializers.CharField(source="deal.deal_number", read_only=True, default=None)
    lines = SupplierOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierOrder
        fields = [
            "id",
            "order_number",
            "supplier",
            "supplier_name",
            "deal",
            "deal_number",
            "procurement_model",
            "status",
            "currency",
            "total_amount",
            "supplier_pi_reference",
            "estimated_dispatch_date",
            "shipping_port",
            "destination_port",
            "freight_payer",
            "customs_payer",
            "notes",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "order_number", "created_at", "updated_at"]
