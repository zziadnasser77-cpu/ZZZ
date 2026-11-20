from decimal import Decimal

from rest_framework import serializers

from apps.catalog.serializers import _build_full_url
from .models import Quotation, QuotationLine, QuotationVersion


class QuotationLineSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.model_name", read_only=True)
    sku = serializers.CharField(source="model.sku", read_only=True)
    product_name_ar = serializers.CharField(source="model.product.name_ar", read_only=True)
    display_image = serializers.SerializerMethodField()
    specifications = serializers.JSONField(source="model.specifications", read_only=True)

    class Meta:
        model = QuotationLine
        fields = [
            "id",
            "version",
            "model",
            "model_name",
            "sku",
            "product_name_ar",
            "display_image",
            "specifications",
            "description",
            "quantity",
            "unit_price",
            "discount_pct",
            "total_price",
            "warranty_months",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "total_price", "created_at", "updated_at"]

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

    def validate(self, attrs):
        qty = attrs.get("quantity", getattr(self.instance, "quantity", 1))
        unit_price = attrs.get("unit_price", getattr(self.instance, "unit_price", Decimal("0.00")))
        disc_pct = attrs.get("discount_pct", getattr(self.instance, "discount_pct", Decimal("0.00")))
        if qty <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
        if unit_price < Decimal("0.00"):
            raise serializers.ValidationError({"unit_price": "Unit price cannot be negative."})
        if disc_pct < Decimal("0.00") or disc_pct > Decimal("100.00"):
            raise serializers.ValidationError({"discount_pct": "Discount must be between 0% and 100%."})

        # Calculate line total
        base_line = Decimal(qty) * unit_price
        disc_amt = (base_line * disc_pct) / Decimal("100.00")
        attrs["total_price"] = round(base_line - disc_amt, 2)
        return attrs


class QuotationVersionSerializer(serializers.ModelSerializer):
    lines = QuotationLineSerializer(many=True, read_only=True)
    approved_by_email = serializers.EmailField(source="approved_by.email", read_only=True, default=None)

    class Meta:
        model = QuotationVersion
        fields = [
            "id",
            "quotation",
            "version_number",
            "status",
            "valid_until",
            "payment_terms",
            "delivery_terms",
            "notes",
            "subtotal",
            "discount_pct",
            "discount_amount",
            "tax_amount",
            "total_amount",
            "requires_approval",
            "approval_reason",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "snapshot",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "version_number",
            "subtotal",
            "discount_amount",
            "total_amount",
            "requires_approval",
            "approval_reason",
            "approved_by",
            "approved_at",
            "snapshot",
            "created_at",
            "updated_at",
        ]


class QuotationSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.legal_name_ar", read_only=True)
    opportunity_title = serializers.CharField(source="opportunity.title", read_only=True, default=None)
    versions = QuotationVersionSerializer(many=True, read_only=True)
    latest_version = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = [
            "id",
            "quotation_number",
            "title",
            "customer",
            "customer_name",
            "opportunity",
            "opportunity_title",
            "commercial_model",
            "currency",
            "current_version_number",
            "status",
            "latest_version",
            "versions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "quotation_number", "current_version_number", "created_at", "updated_at"]

    def get_latest_version(self, obj):
        v = obj.versions.order_by("-version_number").first()
        if v:
            return QuotationVersionSerializer(v).data
        return None
