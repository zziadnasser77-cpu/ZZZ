from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.identity_access.permissions import HasPermission

from .models import (
    CustodyRecord,
    Location,
    OwnershipRecord,
    SerialAsset,
    StockCount,
    StockCountItem,
    StockMovement,
)
from .serializers import (
    CustodyRecordSerializer,
    LocationSerializer,
    OwnershipRecordSerializer,
    SerialAssetSerializer,
    StockCountItemSerializer,
    StockCountSerializer,
    StockMovementSerializer,
)
from .services import (
    post_stock_count,
    record_stock_movement,
    transfer_custody,
    transfer_ownership,
)


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "inventory.location.view",
        "retrieve": "inventory.location.view",
        "create": "inventory.location.create",
        "update": "inventory.location.edit",
        "partial_update": "inventory.location.edit",
        "destroy": "inventory.location.manage",
    }
    search_fields = ["code", "name_ar", "name_en"]
    filterset_fields = ["location_type", "is_active"]


class SerialAssetViewSet(viewsets.ModelViewSet):
    queryset = SerialAsset.objects.select_related("model__product", "current_location").prefetch_related(
        "ownership_history", "custody_history"
    )
    serializer_class = SerialAssetSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "inventory.asset.view",
        "retrieve": "inventory.asset.view",
        "create": "inventory.asset.create",
        "update": "inventory.asset.edit",
        "partial_update": "inventory.asset.edit",
        "destroy": "inventory.asset.manage",
        "transfer_custody": "inventory.custody.create",
        "transfer_ownership": "inventory.ownership.create",
    }
    search_fields = [
        "serial_number",
        "model__model_code",
        "model__model_name",
        "current_owner",
        "current_custodian",
    ]
    filterset_fields = ["status", "current_location", "model"]
    ordering_fields = ["serial_number", "created_at"]

    def perform_create(self, serializer):
        asset = serializer.save()
        # Create initial ownership & custody records
        transfer_ownership(
            asset,
            owner_type=OwnershipRecord.OwnerType.LOCAL_COMPANY,
            owner_name=asset.current_owner,
            proof_document_ref="Initial Inventory Registration",
        )
        transfer_custody(
            asset,
            custodian_type=CustodyRecord.CustodianType.USER,
            custodian_name=asset.current_custodian,
            purpose="Warehouse Initial Storage",
            custodian_user=self.request.user,
        )
        log_event(
            "inventory.asset_created",
            entity=asset,
            summary=f"SerialAsset {asset.serial_number} ({asset.model.model_code})",
        )

    @action(detail=True, methods=["post"], url_path="transfer-custody")
    def transfer_custody(self, request, pk=None):
        asset = self.get_object()
        record = transfer_custody(
            asset,
            custodian_type=request.data.get("custodian_type", CustodyRecord.CustodianType.USER),
            custodian_name=request.data.get("custodian_name", ""),
            purpose=request.data.get("purpose", "Maintenance / Demonstration"),
            custodian_user=request.user,
            notes=request.data.get("notes", ""),
        )
        return Response(CustodyRecordSerializer(record).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="transfer-ownership")
    def transfer_ownership(self, request, pk=None):
        asset = self.get_object()
        record = transfer_ownership(
            asset,
            owner_type=request.data.get("owner_type", OwnershipRecord.OwnerType.CUSTOMER),
            owner_name=request.data.get("owner_name", ""),
            proof_document_ref=request.data.get("proof_document_ref", ""),
            notes=request.data.get("notes", ""),
        )
        return Response(OwnershipRecordSerializer(record).data, status=status.HTTP_200_OK)


class OwnershipRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OwnershipRecord.objects.select_related("asset")
    serializer_class = OwnershipRecordSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "inventory.ownership.view",
        "retrieve": "inventory.ownership.view",
    }
    filterset_fields = ["asset", "owner_type", "is_current"]


class CustodyRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustodyRecord.objects.select_related("asset", "custodian_user")
    serializer_class = CustodyRecordSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "inventory.custody.view",
        "retrieve": "inventory.custody.view",
    }
    filterset_fields = ["asset", "custodian_type", "is_current", "custodian_user"]


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related("model__product", "asset", "from_location", "to_location")
    serializer_class = StockMovementSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "inventory.movement.view",
        "retrieve": "inventory.movement.view",
        "create": "inventory.movement.create",
        "update": "inventory.movement.manage",
        "partial_update": "inventory.movement.manage",
        "destroy": "inventory.movement.manage",
    }
    search_fields = ["movement_number", "reference_document", "model__model_code", "asset__serial_number"]
    filterset_fields = ["movement_type", "from_location", "to_location", "model", "is_posted"]
    ordering_fields = ["created_at", "quantity"]

    def perform_create(self, serializer):
        vd = serializer.validated_data
        record_stock_movement(
            movement_type=vd["movement_type"],
            model=vd["model"],
            quantity=vd["quantity"],
            from_location=vd.get("from_location"),
            to_location=vd.get("to_location"),
            asset=vd.get("asset"),
            unit_cost=vd.get("unit_cost", 0.00),
            reference_document=vd.get("reference_document", ""),
            notes=vd.get("notes", ""),
            user=self.request.user,
        )


class StockCountViewSet(viewsets.ModelViewSet):
    queryset = StockCount.objects.select_related("location", "approved_by").prefetch_related("items__model")
    serializer_class = StockCountSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "inventory.count.view",
        "retrieve": "inventory.count.view",
        "create": "inventory.count.create",
        "update": "inventory.count.edit",
        "partial_update": "inventory.count.edit",
        "destroy": "inventory.count.manage",
        "approve": "inventory.count.approve",
        "post_adjustments": "inventory.count.post",
    }
    search_fields = ["count_number", "location__code", "location__name_ar"]
    filterset_fields = ["status", "location"]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not request.user.has_perm_code("inventory.count.approve"):
            raise PermissionDenied("Approving stock count requires inventory.count.approve permission.")
        sc = self.get_object()
        sc.status = StockCount.Status.APPROVED
        sc.approved_by = request.user
        sc.save(update_fields=["status", "approved_by", "updated_at"])
        log_event(
            "inventory.count_approved",
            entity=sc,
            summary=f"Stock Count {sc.count_number} approved",
            sensitive=True,
        )
        return Response(StockCountSerializer(sc).data)

    @action(detail=True, methods=["post"], url_path="post-adjustments")
    def post_adjustments(self, request, pk=None):
        if not request.user.has_perm_code("inventory.count.post"):
            raise PermissionDenied("Posting adjustments requires inventory.count.post permission.")
        sc = self.get_object()
        post_stock_count(sc, request.user)
        return Response(StockCountSerializer(sc).data)


class StockCountItemViewSet(viewsets.ModelViewSet):
    queryset = StockCountItem.objects.select_related("stock_count", "model")
    serializer_class = StockCountItemSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "inventory.count.view",
        "retrieve": "inventory.count.view",
        "create": "inventory.count.edit",
        "update": "inventory.count.edit",
        "partial_update": "inventory.count.edit",
        "destroy": "inventory.count.edit",
    }
