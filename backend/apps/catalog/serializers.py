from rest_framework import serializers

from .models import Category, Manufacturer, Product, ProductModel


def _build_full_url(url: str | None, request) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if request:
        return request.build_absolute_uri(url)
    clean_path = url if url.startswith("/") else f"/{url}"
    return f"https://smses-backend.onrender.com{clean_path}"


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
        img = None
        if obj.image:
            img = obj.image.url
        elif obj.image_url:
            img = obj.image_url
        elif hasattr(obj, "product") and obj.product:
            if obj.product.image:
                img = obj.product.image.url
            elif obj.product.image_url:
                img = obj.product.image_url
        return _build_full_url(img, request)

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
        img = None
        if obj.image:
            img = obj.image.url
        elif obj.image_url:
            img = obj.image_url
        else:
            first_model = obj.models.first()
            if first_model:
                if first_model.image:
                    img = first_model.image.url
                elif first_model.image_url:
                    img = first_model.image_url
        return _build_full_url(img, request)
