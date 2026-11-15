from decimal import Decimal

from rest_framework import serializers

from .models import PriceList, PriceListItem


class PriceListItemSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.model_name", read_only=True)
    sku = serializers.CharField(source="model.sku", read_only=True)
    product_name_ar = serializers.CharField(source="model.product.name_ar", read_only=True)
    display_image = serializers.SerializerMethodField()
    margin_pct = serializers.SerializerMethodField()

    class Meta:
        model = PriceListItem
        fields = [
            "id",
            "price_list",
            "model",
            "model_name",
            "sku",
            "product_name_ar",
            "display_image",
            "base_price",
            "min_price",
            "cost_price",
            "margin_pct",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_display_image(self, obj):
        if not obj.model:
            return None
        request = self.context.get("request")
        if obj.model.image:
            return request.build_absolute_uri(obj.model.image.url) if request else obj.model.image.url
        if obj.model.image_url:
            return obj.model.image_url
        if hasattr(obj.model, "product") and obj.model.product:
            if obj.model.product.image:
                return request.build_absolute_uri(obj.model.product.image.url) if request else obj.model.product.image.url
            if obj.model.product.image_url:
                return obj.model.product.image_url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        # Enforce field-level security for supplier cost (Spec §9, ADR-006)
        has_cost_perm = bool(request and request.user and request.user.has_perm_code("pricing.cost.view"))
        if not has_cost_perm:
            data.pop("cost_price", None)
            data.pop("margin_pct", None)
        return data

    def get_margin_pct(self, obj):
        request = self.context.get("request")
        if not (request and request.user and request.user.has_perm_code("pricing.cost.view")):
            return None
        if obj.cost_price and obj.base_price and obj.base_price > Decimal("0.00"):
            margin = ((obj.base_price - obj.cost_price) / obj.base_price) * Decimal("100.00")
            return float(round(margin, 2))
        return None

    def validate(self, attrs):
        base_price = attrs.get("base_price", getattr(self.instance, "base_price", None))
        min_price = attrs.get("min_price", getattr(self.instance, "min_price", None))
        if base_price is not None and min_price is not None and min_price > base_price:
            raise serializers.ValidationError(
                {"min_price": "Minimum price cannot be greater than base price."}
            )
        return attrs


class PriceListSerializer(serializers.ModelSerializer):
    items = PriceListItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = PriceList
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "currency",
            "effective_from",
            "effective_to",
            "status",
            "is_active",
            "is_default",
            "description",
            "items_count",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
