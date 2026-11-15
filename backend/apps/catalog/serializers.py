from rest_framework import serializers

from .models import Category, Manufacturer, Product, ProductModel


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "code", "name_ar", "name_en", "parent", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "country",
            "website",
            "is_primary_partner",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductModelSerializer(serializers.ModelSerializer):
    product_name_ar = serializers.CharField(source="product.name_ar", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    approved_by_email = serializers.EmailField(source="approved_by.email", read_only=True, default=None)
    approved_price = serializers.SerializerMethodField()
    display_image = serializers.SerializerMethodField()

    class Meta:
        model = ProductModel
        fields = [
            "id",
            "product",
            "product_name_ar",
            "product_code",
            "model_code",
            "model_name",
            "sku",
            "specifications",
            "standard_warranty_months",
            "standard_accessories",
            "optional_accessories",
            "power_requirements",
            "origin_country",
            "image",
            "image_url",
            "display_image",
            "approval_status",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "approved_price",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "approved_by", "approved_at", "created_at", "updated_at"]

    def get_display_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        if obj.image_url:
            return obj.image_url
        if hasattr(obj, "product") and obj.product:
            if obj.product.image:
                return request.build_absolute_uri(obj.product.image.url) if request else obj.product.image.url
            if obj.product.image_url:
                return obj.product.image_url
        return None

    def get_approved_price(self, obj):
        item = obj.price_list_items.filter(price_list__is_active=True, price_list__is_default=True).first()
        if not item:
            item = obj.price_list_items.filter(price_list__is_active=True).first()
        if item:
            return {
                "base_price": str(item.base_price),
                "min_price": str(item.min_price),
                "currency": item.price_list.currency,
                "price_list_code": item.price_list.code,
            }
        return None


class ProductSerializer(serializers.ModelSerializer):
    category_name_ar = serializers.CharField(source="category.name_ar", read_only=True)
    manufacturer_name_ar = serializers.CharField(source="manufacturer.name_ar", read_only=True)
    models = ProductModelSerializer(many=True, read_only=True)
    display_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "category",
            "category_name_ar",
            "manufacturer",
            "manufacturer_name_ar",
            "device_class",
            "description_ar",
            "description_en",
            "image",
            "image_url",
            "display_image",
            "is_active",
            "models",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_display_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        if obj.image_url:
            return obj.image_url
        first_model = obj.models.first()
        if first_model:
            if first_model.image:
                return request.build_absolute_uri(first_model.image.url) if request else first_model.image.url
            if first_model.image_url:
                return first_model.image_url
        return None
