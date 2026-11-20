from rest_framework import serializers

from apps.catalog.serializers import _build_full_url

from apps.common.serializers import CostRestrictedMixin

from .models import (
    CustodyRecord,
    Location,
    OwnershipRecord,
    SerialAsset,
    StockCount,
    StockCountItem,
    StockMovement,
)


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "location_type",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OwnershipRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnershipRecord
        fields = [
            "id",
            "asset",
            "owner_type",
            "owner_name",
            "effective_from",
            "effective_to",
            "proof_document_ref",
            "is_current",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CustodyRecordSerializer(serializers.ModelSerializer):
    custodian_user_email = serializers.EmailField(source="custodian_user.email", read_only=True, default=None)

    class Meta:
        model = CustodyRecord
        fields = [
            "id",
            "asset",
            "custodian_type",
            "custodian_user",
            "custodian_user_email",
            "custodian_name",
            "effective_from",
            "effective_to",
            "purpose",
            "is_current",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SerialAssetSerializer(CostRestrictedMixin, serializers.ModelSerializer):
    cost_fields = ('cost_price',)
    model_name = serializers.CharField(source="model.model_name", read_only=True)
    sku = serializers.CharField(source="model.sku", read_only=True)
    location_name = serializers.CharField(source="current_location.name_ar", read_only=True)
    display_image = serializers.SerializerMethodField()
    current_ownership = serializers.SerializerMethodField()
    current_custody = serializers.SerializerMethodField()

    class Meta:
        model = SerialAsset
        fields = [
            "id",
            "serial_number",
            "model",
            "model_name",
            "sku",
            "display_image",
            "current_location",
            "location_name",
            "current_owner",
            "current_custodian",
            "status",
            "manufacture_date",
            "cost_price",
            "notes",
            "current_ownership",
            "current_custody",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "current_owner", "current_custodian", "created_at", "updated_at"]

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

    def get_current_ownership(self, obj):
        rec = obj.ownership_history.filter(is_current=True).first()
        if rec:
            return OwnershipRecordSerializer(rec).data
        return None

    def get_current_custody(self, obj):
        rec = obj.custody_history.filter(is_current=True).first()
        if rec:
            return CustodyRecordSerializer(rec).data
        return None


class StockMovementSerializer(CostRestrictedMixin, serializers.ModelSerializer):
    cost_fields = ('unit_cost', 'total_cost')
    model_name = serializers.CharField(source="model.model_name", read_only=True)
    sku = serializers.CharField(source="model.sku", read_only=True)
    from_location_code = serializers.CharField(source="from_location.code", read_only=True, default=None)
    to_location_code = serializers.CharField(source="to_location.code", read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "movement_number",
            "movement_type",
            "model",
            "model_name",
            "sku",
            "asset",
            "from_location",
            "from_location_code",
            "to_location",
            "to_location_code",
            "quantity",
            "unit_cost",
            "total_cost",
            "reference_document",
            "is_posted",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "movement_number", "total_cost", "is_posted", "created_at", "updated_at"]


class StockCountItemSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.model_name", read_only=True)
    sku = serializers.CharField(source="model.sku", read_only=True)

    class Meta:
        model = StockCountItem
        fields = [
            "id",
            "stock_count",
            "model",
            "model_name",
            "sku",
            "system_quantity",
            "counted_quantity",
            "discrepancy_quantity",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "discrepancy_quantity", "created_at", "updated_at"]


class StockCountSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name_ar", read_only=True)
    items = StockCountItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockCount
        fields = [
            "id",
            "count_number",
            "location",
            "location_name",
            "status",
            "count_date",
            "approved_by",
            "notes",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "count_number", "approved_by", "created_at", "updated_at"]
