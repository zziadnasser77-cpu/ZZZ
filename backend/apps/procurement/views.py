from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.identity_access.permissions import HasPermission

from .models import Supplier, SupplierOrder, SupplierOrderLine
from .serializers import (
    SupplierOrderLineSerializer,
    SupplierOrderSerializer,
    SupplierSerializer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "procurement.supplier.view",
        "retrieve": "procurement.supplier.view",
        "create": "procurement.supplier.create",
        "update": "procurement.supplier.edit",
        "partial_update": "procurement.supplier.edit",
        "destroy": "procurement.supplier.manage",
    }
    search_fields = ["code", "name_ar", "name_en", "contact_person"]
    filterset_fields = ["is_primary_partner", "is_active", "country"]

    def perform_create(self, serializer):
        sup = serializer.save()
        log_event("procurement.supplier_created", entity=sup, summary=f"Supplier {sup.code}: {sup.name_ar}")

    def perform_update(self, serializer):
        sup = serializer.save()
        log_event("procurement.supplier_updated", entity=sup, summary=f"Supplier {sup.code} updated")


class SupplierOrderViewSet(viewsets.ModelViewSet):
    queryset = SupplierOrder.objects.select_related("supplier", "deal").prefetch_related("lines__model")
    serializer_class = SupplierOrderSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "procurement.order.view",
        "retrieve": "procurement.order.view",
        "create": "procurement.order.create",
        "update": "procurement.order.edit",
        "partial_update": "procurement.order.edit",
        "destroy": "procurement.order.manage",
        "confirm_pi": "procurement.order.edit",
    }
    search_fields = ["order_number", "supplier_pi_reference", "supplier__name_ar", "deal__deal_number"]
    filterset_fields = ["procurement_model", "status", "supplier", "currency"]
    ordering_fields = ["created_at", "total_amount", "estimated_dispatch_date"]

    def perform_create(self, serializer):
        po = serializer.save()
        log_event("procurement.order_created", entity=po, summary=f"Supplier Order {po.order_number}")

    def perform_update(self, serializer):
        po = serializer.save()
        log_event("procurement.order_updated", entity=po, summary=f"Supplier Order {po.order_number} updated")

    @action(detail=True, methods=["post"], url_path="confirm-pi")
    def confirm_pi(self, request, pk=None):
        po = self.get_object()
        pi_ref = request.data.get("supplier_pi_reference")
        if pi_ref:
            po.supplier_pi_reference = pi_ref
        po.status = SupplierOrder.Status.CONFIRMED_BY_SUPPLIER
        po.save(update_fields=["supplier_pi_reference", "status", "updated_at"])
        log_event(
            "procurement.order_confirmed_by_supplier",
            entity=po,
            summary=f"Supplier Order {po.order_number} PI confirmed: {po.supplier_pi_reference}",
            sensitive=True,
        )
        return Response(SupplierOrderSerializer(po).data, status=status.HTTP_200_OK)


class SupplierOrderLineViewSet(viewsets.ModelViewSet):
    queryset = SupplierOrderLine.objects.select_related("order", "model")
    serializer_class = SupplierOrderLineSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "procurement.order.view",
        "retrieve": "procurement.order.view",
        "create": "procurement.order.edit",
        "update": "procurement.order.edit",
        "partial_update": "procurement.order.edit",
        "destroy": "procurement.order.edit",
    }
