from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation
from apps.identity_access.permissions import HasPermission
from apps.quotations.models import Quotation

from .models import Deal, SalesOrder, SalesOrderLine
from .serializers import DealSerializer, SalesOrderLineSerializer, SalesOrderSerializer
from .services import convert_quotation_to_deal_and_order


class DealViewSet(viewsets.ModelViewSet):
    queryset = Deal.objects.select_related("customer", "quotation").prefetch_related(
        "sales_orders__lines__model"
    )
    serializer_class = DealSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "sales_orders.deal.view",
        "retrieve": "sales_orders.deal.view",
        "create": "sales_orders.deal.create",
        "update": "sales_orders.deal.edit",
        "partial_update": "sales_orders.deal.edit",
        "destroy": "sales_orders.deal.manage",
        "from_quotation": "sales_orders.deal.create",
    }
    search_fields = ["deal_number", "title", "customer__legal_name_ar", "seller_of_record"]
    filterset_fields = ["commercial_model", "status", "currency", "customer"]
    ordering_fields = ["created_at", "total_value"]

    def perform_create(self, serializer):
        deal = serializer.save()
        log_event("sales_orders.deal_created", entity=deal, summary=f"Deal {deal.deal_number}: {deal.title}")

    def perform_update(self, serializer):
        deal = serializer.save()
        log_event("sales_orders.deal_updated", entity=deal, summary=f"Deal {deal.deal_number} updated")

    @action(detail=False, methods=["post"], url_path="from-quotation")
    def from_quotation(self, request):
        quotation_id = request.data.get("quotation_id")
        if not quotation_id:
            raise BusinessRuleViolation("quotation_id is required.")
        quotation = Quotation.objects.filter(pk=quotation_id).first()
        if not quotation:
            raise BusinessRuleViolation("Quotation not found.")
        deal, so = convert_quotation_to_deal_and_order(quotation, request.user)
        return Response(DealSerializer(deal).data, status=status.HTTP_201_CREATED)


class SalesOrderViewSet(viewsets.ModelViewSet):
    queryset = SalesOrder.objects.select_related("deal", "customer").prefetch_related("lines__model")
    serializer_class = SalesOrderSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "sales_orders.order.view",
        "retrieve": "sales_orders.order.view",
        "create": "sales_orders.order.create",
        "update": "sales_orders.order.edit",
        "partial_update": "sales_orders.order.edit",
        "destroy": "sales_orders.order.manage",
    }
    search_fields = ["order_number", "customer__legal_name_ar", "deal__deal_number"]
    filterset_fields = ["status", "deal", "customer"]
    ordering_fields = ["created_at", "total_amount"]

    def perform_create(self, serializer):
        so = serializer.save()
        log_event("sales_orders.order_created", entity=so, summary=f"Sales Order {so.order_number}")

    def perform_update(self, serializer):
        so = serializer.save()
        log_event("sales_orders.order_updated", entity=so, summary=f"Sales Order {so.order_number} updated")


class SalesOrderLineViewSet(viewsets.ModelViewSet):
    queryset = SalesOrderLine.objects.select_related("order", "model")
    serializer_class = SalesOrderLineSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "sales_orders.order.view",
        "retrieve": "sales_orders.order.view",
        "create": "sales_orders.order.edit",
        "update": "sales_orders.order.edit",
        "partial_update": "sales_orders.order.edit",
        "destroy": "sales_orders.order.edit",
    }
