from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.biomedical.models import (
    InstallationProtocol,
    ServiceTicket,
    SparePartRequest,
    WarrantyContract,
)
from apps.biomedical.serializers import (
    InstallationProtocolSerializer,
    ServiceTicketSerializer,
    ServiceVisitSerializer,
    SparePartRequestSerializer,
    WarrantyContractSerializer,
)
from apps.biomedical.services import (
    approve_spare_part,
    assign_service_ticket,
    close_service_ticket,
    record_service_visit,
    request_spare_part,
    sign_installation_protocol,
)
from apps.common.exceptions import BusinessRuleViolation
from apps.identity_access.permissions import HasPermission

User = get_user_model()


class InstallationProtocolViewSet(viewsets.ModelViewSet):
    queryset = InstallationProtocol.objects.select_related(
        "asset__model", "customer", "location", "lead_engineer"
    ).all()
    serializer_class = InstallationProtocolSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "biomedical.protocol.view",
        "retrieve": "biomedical.protocol.view",
        "create": "biomedical.protocol.create",
        "update": "biomedical.protocol.edit",
        "partial_update": "biomedical.protocol.edit",
        "destroy": "biomedical.protocol.manage",
        "sign": "biomedical.protocol.approve",
    }
    filterset_fields = ["status", "customer", "lead_engineer"]
    search_fields = ["protocol_number", "asset__serial_number", "customer__legal_name_ar"]

    @action(detail=True, methods=["post"])
    def sign(self, request, pk=None):
        protocol = self.get_object()
        rep_name = request.data.get("customer_representative_name")
        rep_title = request.data.get("customer_representative_title", "")
        if not rep_name:
            raise BusinessRuleViolation("يجب إدخال اسم ممثل العميل المستلم للجهاز.")

        sign_installation_protocol(
            protocol, representative_name=rep_name, representative_title=rep_title, user=request.user
        )
        protocol.refresh_from_db()
        return Response(InstallationProtocolSerializer(protocol, context={"request": request}).data)


class WarrantyContractViewSet(viewsets.ModelViewSet):
    queryset = WarrantyContract.objects.select_related("asset__model", "customer").all()
    serializer_class = WarrantyContractSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "biomedical.warranty.view",
        "retrieve": "biomedical.warranty.view",
        "create": "biomedical.warranty.create",
        "update": "biomedical.warranty.edit",
        "partial_update": "biomedical.warranty.edit",
        "destroy": "biomedical.warranty.manage",
    }
    filterset_fields = ["warranty_type", "is_active", "customer", "asset"]
    search_fields = ["contract_number", "asset__serial_number"]


class ServiceTicketViewSet(viewsets.ModelViewSet):
    queryset = (
        ServiceTicket.objects.select_related("asset__model", "customer", "assigned_engineer", "created_by")
        .prefetch_related("visits__engineer", "spare_parts__approved_by")
        .all()
    )
    serializer_class = ServiceTicketSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "biomedical.ticket.view",
        "retrieve": "biomedical.ticket.view",
        "create": "biomedical.ticket.create",
        "update": "biomedical.ticket.edit",
        "partial_update": "biomedical.ticket.edit",
        "destroy": "biomedical.ticket.cancel",
        "assign": "biomedical.ticket.edit",
        "add_visit": "biomedical.ticket.edit",
        "request_part": "biomedical.ticket.edit",
        "close": "biomedical.ticket.approve",
    }
    filterset_fields = [
        "status",
        "ticket_type",
        "priority",
        "warranty_status",
        "assigned_engineer",
        "customer",
    ]
    search_fields = ["ticket_number", "title", "asset__serial_number", "customer__legal_name_ar"]

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        engineer_id = request.data.get("engineer_id")
        if not engineer_id:
            raise BusinessRuleViolation("يجب تحديد المهندس المكلف.")
        engineer = User.objects.get(pk=engineer_id)
        assign_service_ticket(ticket, engineer=engineer, user=request.user)
        ticket.refresh_from_db()
        return Response(ServiceTicketSerializer(ticket, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def add_visit(self, request, pk=None):
        ticket = self.get_object()
        actions_taken = request.data.get("actions_taken")
        if not actions_taken:
            raise BusinessRuleViolation("يجب كتابة الإجراءات المتخذة في الزيارة.")
        diagnostic = request.data.get("diagnostic_details", "")
        is_resolved = bool(request.data.get("is_resolved", False))
        customer_sign = request.data.get("customer_sign_off_name", "")

        visit = record_service_visit(
            ticket=ticket,
            engineer=request.user,
            actions_taken=actions_taken,
            diagnostic_details=diagnostic,
            is_resolved=is_resolved,
            customer_sign_off_name=customer_sign,
            user=request.user,
        )
        return Response(ServiceVisitSerializer(visit).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def request_part(self, request, pk=None):
        ticket = self.get_object()
        part_name = request.data.get("part_name")
        if not part_name:
            raise BusinessRuleViolation("يجب إدخال اسم قطعة الغيار المطلوبة.")
        part_sku = request.data.get("part_sku", "")
        quantity = int(request.data.get("quantity", 1))
        coverage = request.data.get("coverage", SparePartRequest.Coverage.WARRANTY_FREE)

        req = request_spare_part(
            ticket=ticket,
            part_name=part_name,
            part_sku=part_sku,
            quantity=quantity,
            coverage=coverage,
            user=request.user,
        )
        return Response(SparePartRequestSerializer(req).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        ticket = self.get_object()
        labor_hours = Decimal(str(request.data.get("labor_hours", "0.00")))
        labor_cost = Decimal(str(request.data.get("labor_cost", "0.00")))
        resolution = request.data.get("resolution", "")
        close_service_ticket(
            ticket, labor_hours=labor_hours, labor_cost=labor_cost, resolution=resolution, user=request.user
        )
        ticket.refresh_from_db()
        return Response(ServiceTicketSerializer(ticket, context={"request": request}).data)


class SparePartRequestViewSet(viewsets.ModelViewSet):
    queryset = SparePartRequest.objects.select_related("ticket", "approved_by").all()
    serializer_class = SparePartRequestSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "biomedical.part_request.view",
        "retrieve": "biomedical.part_request.view",
        "create": "biomedical.part_request.create",
        "update": "biomedical.part_request.edit",
        "partial_update": "biomedical.part_request.edit",
        "destroy": "biomedical.part_request.manage",
        "approve": "biomedical.part_request.approve",
    }
    filterset_fields = ["status", "coverage", "ticket"]
    search_fields = ["part_name", "part_sku"]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        part_req = self.get_object()
        cost = Decimal(str(request.data.get("cost_price", "0.00")))
        customer_price = Decimal(str(request.data.get("customer_price", "0.00")))
        approve_spare_part(part_req, cost_price=cost, customer_price=customer_price, user=request.user)
        part_req.refresh_from_db()
        return Response(SparePartRequestSerializer(part_req).data)
