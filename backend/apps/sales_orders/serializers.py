from rest_framework import serializers

from apps.catalog.serializers import _build_full_url
from .models import Deal, SalesOrder, SalesOrderLine


class SalesOrderLineSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.model_name", read_only=True)
    sku = serializers.CharField(source="model.sku", read_only=True)
    display_image = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrderLine
        fields = [
            "id",
            "order",
            "model",
            "model_name",
            "sku",
            "display_image",
            "description",
            "quantity",
            "unit_price",
            "total_price",
            "delivered_quantity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_display_image(self, obj):
        if not obj.model:
            return None
        request = self.context.get("request")
        img = None
        if obj.model.image:
            img = obj.model.image.url
        elif obj.model.image_url:
            img = obj.model.image_url
        elif hasattr(obj.model, "product") and obj.model.product:
            if obj.model.product.image:
                img = obj.model.product.image.url
            elif obj.model.product.image_url:
                img = obj.model.product.image_url
        return _build_full_url(img, request)


class SalesOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    deal_number = serializers.CharField(source="deal.deal_number", read_only=True)
    lines = SalesOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = SalesOrder
        fields = [
            "id",
            "order_number",
            "deal",
            "deal_number",
            "customer",
            "customer_name",
            "status",
            "currency",
            "total_amount",
            "delivery_terms",
            "payment_terms",
            "notes",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "order_number", "created_at", "updated_at"]


class DealSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    quotation_number = serializers.CharField(
        source="quotation.quotation_number", read_only=True, default=None
    )
    sales_orders = SalesOrderSerializer(many=True, read_only=True)

    class Meta:
        model = Deal
        fields = [
            "id",
            "deal_number",
            "title",
            "customer",
            "customer_name",
            "quotation",
            "quotation_number",
            "commercial_model",
            "seller_of_record",
            "invoice_issuer",
            "payment_recipient",
            "currency",
            "total_value",
            "commission_rate_pct",
            "expected_commission_amount",
            "status",
            "notes",
            "sales_orders",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "deal_number", "created_at", "updated_at"]
