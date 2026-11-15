from decimal import Decimal

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation
from apps.identity_access.permissions import HasPermission

from .models import Quotation, QuotationLine, QuotationVersion
from .serializers import (
    QuotationLineSerializer,
    QuotationSerializer,
    QuotationVersionSerializer,
)
from .services import (
    approve_quotation_version,
    build_version_snapshot,
    evaluate_version_approval,
    recalculate_version_totals,
)


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.select_related("customer", "opportunity").prefetch_related(
        "versions__lines__model__product"
    )
    serializer_class = QuotationSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "quotations.quotation.view",
        "retrieve": "quotations.quotation.view",
        "create": "quotations.quotation.create",
        "update": "quotations.quotation.edit",
        "partial_update": "quotations.quotation.edit",
        "destroy": "quotations.quotation.manage",
        "send": "quotations.quotation.edit",
        "accept": "quotations.quotation.edit",
        "reject": "quotations.quotation.edit",
    }
    search_fields = ["quotation_number", "title", "customer__legal_name_ar"]
    filterset_fields = ["commercial_model", "currency", "status", "customer"]
    ordering_fields = ["created_at", "quotation_number"]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        lines_data = request.data.get("lines", [])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quotation = serializer.save()

        # Automatically create Version 1 with lines if provided
        version = QuotationVersion.objects.create(
            quotation=quotation,
            version_number=1,
            status=QuotationVersion.Status.DRAFT,
            notes=request.data.get("notes", ""),
            payment_terms=request.data.get("payment_terms", "100% الدفع مقدماً بحوالة بنكية T/T"),
            delivery_terms=request.data.get("delivery_terms", "شامل التوريد والتركيب والتشغيل والضمان في الموقع"),
        )
        for ld in lines_data:
            model_id = ld.get("model")
            if not model_id:
                continue
            qty = int(ld.get("quantity", 1))
            unit_price = Decimal(str(ld.get("unit_price", "0.00")))
            disc = Decimal(str(ld.get("discount_pct", "0.00")))
            warranty = int(ld.get("warranty_months", 24))
            base_tot = Decimal(qty) * unit_price
            disc_amt = (base_tot * disc) / Decimal("100.00")
            tot = round(base_tot - disc_amt, 2)
            QuotationLine.objects.create(
                version=version,
                model_id=model_id,
                description=ld.get("description", ""),
                quantity=qty,
                unit_price=unit_price,
                discount_pct=disc,
                total_price=tot,
                warranty_months=warranty,
            )
        recalculate_version_totals(version)
        evaluate_version_approval(version, request.user)
        log_event("quotations.created", entity=quotation, summary=f"Quotation {quotation.quotation_number}")
        quotation.refresh_from_db()
        return Response(QuotationSerializer(quotation).data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        pass

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        quotation = self.get_object()
        latest = quotation.versions.order_by("-version_number").first()
        if not latest:
            raise BusinessRuleViolation("Quotation has no versions.")
        if latest.requires_approval and latest.status != QuotationVersion.Status.APPROVED:
            raise BusinessRuleViolation("Cannot send quotation while pending approval.")
        if not latest.snapshot:
            latest.snapshot = build_version_snapshot(latest)
        latest.status = QuotationVersion.Status.SENT
        latest.save(update_fields=["status", "snapshot", "updated_at"])
        quotation.status = Quotation.Status.SENT
        quotation.save(update_fields=["status", "updated_at"])
        log_event(
            "quotations.sent",
            entity=quotation,
            summary=f"Quotation {quotation.quotation_number} sent to customer",
        )
        return Response(QuotationSerializer(quotation).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        quotation = self.get_object()
        latest = quotation.versions.order_by("-version_number").first()
        if latest:
            latest.status = QuotationVersion.Status.ACCEPTED
            latest.save(update_fields=["status", "updated_at"])
        quotation.status = Quotation.Status.ACCEPTED
        quotation.save(update_fields=["status", "updated_at"])
        log_event(
            "quotations.accepted",
            entity=quotation,
            summary=f"Quotation {quotation.quotation_number} accepted",
            sensitive=True,
        )
        return Response(QuotationSerializer(quotation).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        quotation = self.get_object()
        latest = quotation.versions.order_by("-version_number").first()
        if latest:
            latest.status = QuotationVersion.Status.REJECTED
            latest.save(update_fields=["status", "updated_at"])
        quotation.status = Quotation.Status.REJECTED
        quotation.save(update_fields=["status", "updated_at"])
        log_event(
            "quotations.rejected",
            entity=quotation,
            summary=f"Quotation {quotation.quotation_number} rejected",
        )
        return Response(QuotationSerializer(quotation).data)


class QuotationVersionViewSet(viewsets.ModelViewSet):
    queryset = QuotationVersion.objects.select_related("quotation", "approved_by").prefetch_related(
        "lines__model__product"
    )
    serializer_class = QuotationVersionSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "quotations.quotation.view",
        "retrieve": "quotations.quotation.view",
        "create": "quotations.quotation.create",
        "update": "quotations.quotation.edit",
        "partial_update": "quotations.quotation.edit",
        "destroy": "quotations.quotation.manage",
        "approve": "quotations.quotation.approve",
        "new_version": "quotations.quotation.create",
    }

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not request.user.has_perm_code("quotations.quotation.approve"):
            raise PermissionDenied("Approving quotations requires quotations.quotation.approve permission.")
        version = self.get_object()
        approve_quotation_version(version, request.user)
        return Response(QuotationVersionSerializer(version).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def new_version(self, request, pk=None):
        current = self.get_object()
        q = current.quotation
        new_vnum = q.current_version_number + 1
        q.current_version_number = new_vnum
        q.status = Quotation.Status.DRAFT
        q.save(update_fields=["current_version_number", "status", "updated_at"])

        # Mark previous version as superseded
        current.status = QuotationVersion.Status.SUPERSEDED
        current.save(update_fields=["status", "updated_at"])

        new_v = QuotationVersion.objects.create(
            quotation=q,
            version_number=new_vnum,
            status=QuotationVersion.Status.DRAFT,
            valid_until=current.valid_until,
            payment_terms=current.payment_terms,
            delivery_terms=current.delivery_terms,
            notes=current.notes,
            discount_pct=current.discount_pct,
        )
        # Copy lines
        for line in current.lines.all():
            QuotationLine.objects.create(
                version=new_v,
                model=line.model,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                total_price=line.total_price,
                warranty_months=line.warranty_months,
            )
        recalculate_version_totals(new_v)
        evaluate_version_approval(new_v, request.user)
        log_event(
            "quotations.version_created",
            entity=q,
            summary=f"Quotation {q.quotation_number} new version v{new_vnum} created",
        )
        return Response(QuotationVersionSerializer(new_v).data, status=status.HTTP_201_CREATED)


class QuotationLineViewSet(viewsets.ModelViewSet):
    queryset = QuotationLine.objects.select_related("version__quotation", "model__product")
    serializer_class = QuotationLineSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "quotations.quotation.view",
        "retrieve": "quotations.quotation.view",
        "create": "quotations.quotation.edit",
        "update": "quotations.quotation.edit",
        "partial_update": "quotations.quotation.edit",
        "destroy": "quotations.quotation.edit",
    }

    def _check_version_editable(self, version: QuotationVersion):
        if version.status in (
            QuotationVersion.Status.APPROVED,
            QuotationVersion.Status.SENT,
            QuotationVersion.Status.ACCEPTED,
        ):
            raise BusinessRuleViolation(
                "Cannot modify lines of an approved or sent quotation version. Create a new version."
            )

    def perform_create(self, serializer):
        version = serializer.validated_data["version"]
        self._check_version_editable(version)
        serializer.save()
        recalculate_version_totals(version)
        evaluate_version_approval(version, self.request.user)
        log_event(
            "quotations.line_added",
            entity=version.quotation,
            summary=f"Line added to {version.quotation.quotation_number}",
        )

    def perform_update(self, serializer):
        version = serializer.instance.version
        self._check_version_editable(version)
        serializer.save()
        recalculate_version_totals(version)
        evaluate_version_approval(version, self.request.user)
        log_event(
            "quotations.line_updated",
            entity=version.quotation,
            summary=f"Line updated in {version.quotation.quotation_number}",
        )

    def perform_destroy(self, instance):
        version = instance.version
        self._check_version_editable(version)
        instance.delete()
        recalculate_version_totals(version)
        evaluate_version_approval(version, self.request.user)
