from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.identity_access.permissions import HasPermission

from .models import Category, Manufacturer, Product, ProductModel
from .serializers import (
    CategorySerializer,
    ManufacturerSerializer,
    ProductModelSerializer,
    ProductSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "catalog.category.view",
        "retrieve": "catalog.category.view",
        "create": "catalog.category.create",
        "update": "catalog.category.edit",
        "partial_update": "catalog.category.edit",
        "destroy": "catalog.category.manage",
    }
    search_fields = ["code", "name_ar", "name_en"]
    filterset_fields = ["is_active", "parent"]

    def perform_create(self, serializer):
        cat = serializer.save()
        log_event("catalog.category_created", entity=cat, summary=f"Category {cat.code}")

    def perform_update(self, serializer):
        cat = serializer.save()
        log_event("catalog.category_updated", entity=cat, summary=f"Category {cat.code} updated")


class ManufacturerViewSet(viewsets.ModelViewSet):
    queryset = Manufacturer.objects.all()
    serializer_class = ManufacturerSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "catalog.manufacturer.view",
        "retrieve": "catalog.manufacturer.view",
        "create": "catalog.manufacturer.create",
        "update": "catalog.manufacturer.edit",
        "partial_update": "catalog.manufacturer.edit",
        "destroy": "catalog.manufacturer.manage",
    }
    search_fields = ["code", "name_ar", "name_en", "country"]
    filterset_fields = ["country", "is_primary_partner"]

    def perform_create(self, serializer):
        mfg = serializer.save()
        log_event("catalog.manufacturer_created", entity=mfg, summary=f"Manufacturer {mfg.code}")

    def perform_update(self, serializer):
        mfg = serializer.save()
        log_event("catalog.manufacturer_updated", entity=mfg, summary=f"Manufacturer {mfg.code} updated")


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category", "manufacturer").prefetch_related(
        "models__price_list_items__price_list"
    )
    serializer_class = ProductSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "catalog.product.view",
        "retrieve": "catalog.product.view",
        "create": "catalog.product.create",
        "update": "catalog.product.edit",
        "partial_update": "catalog.product.edit",
        "destroy": "catalog.product.manage",
    }
    search_fields = ["code", "name_ar", "name_en", "description_ar", "models__model_name", "models__sku"]
    filterset_fields = ["category", "manufacturer", "device_class", "is_active"]
    ordering_fields = ["code", "created_at"]

    def perform_create(self, serializer):
        prod = serializer.save()
        log_event("catalog.product_created", entity=prod, summary=f"Product {prod.code}")

    def perform_update(self, serializer):
        prod = serializer.save()
        log_event("catalog.product_updated", entity=prod, summary=f"Product {prod.code} updated")


class ProductModelViewSet(viewsets.ModelViewSet):
    queryset = ProductModel.objects.select_related("product", "approved_by").prefetch_related(
        "price_list_items__price_list"
    )
    serializer_class = ProductModelSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "catalog.model.view",
        "retrieve": "catalog.model.view",
        "create": "catalog.model.create",
        "update": "catalog.model.edit",
        "partial_update": "catalog.model.edit",
        "destroy": "catalog.model.manage",
        "approve": "catalog.model.approve",
    }
    search_fields = ["model_code", "model_name", "sku", "product__name_ar"]
    filterset_fields = ["product", "approval_status", "is_active", "origin_country"]
    ordering_fields = ["model_code", "created_at"]

    def perform_create(self, serializer):
        model = serializer.save()
        log_event("catalog.model_created", entity=model, summary=f"Model {model.sku}")

    def perform_update(self, serializer):
        model = serializer.save()
        log_event("catalog.model_updated", entity=model, summary=f"Model {model.sku} updated")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not request.user.has_perm_code("catalog.model.approve"):
            raise PermissionDenied("Approval requires catalog.model.approve permission.")
        model = self.get_object()
        model.approval_status = ProductModel.ApprovalStatus.APPROVED
        model.approved_by = request.user
        model.approved_at = timezone.now()
        model.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])
        log_event(
            "catalog.model_approved", entity=model, summary=f"Model {model.sku} approved", sensitive=True
        )
        return Response(ProductModelSerializer(model).data, status=status.HTTP_200_OK)
