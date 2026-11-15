from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.identity_access.permissions import HasPermission

from .models import Shipment, ShipmentDocument, ShipmentEvent
from .serializers import (
    ShipmentDocumentSerializer,
    ShipmentEventSerializer,
    ShipmentSerializer,
)


class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = Shipment.objects.select_related("supplier_order", "sales_order").prefetch_related(
        "documents", "events"
    )
    serializer_class = ShipmentSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "shipments.shipment.view",
        "retrieve": "shipments.shipment.view",
        "create": "shipments.shipment.create",
        "update": "shipments.shipment.edit",
        "partial_update": "shipments.shipment.edit",
        "destroy": "shipments.shipment.manage",
        "update_status": "shipments.shipment.edit",
    }
    search_fields = ["shipment_number", "tracking_number", "carrier_name"]
    filterset_fields = ["status", "shipping_method", "origin_port", "destination_port"]
    ordering_fields = ["created_at", "estimated_arrival"]

    def perform_create(self, serializer):
        shp = serializer.save()
        log_event(
            "shipments.created", entity=shp, summary=f"Shipment {shp.shipment_number} ({shp.carrier_name})"
        )

    def perform_update(self, serializer):
        shp = serializer.save()
        log_event("shipments.updated", entity=shp, summary=f"Shipment {shp.shipment_number} updated")

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        shp = self.get_object()
        new_status = request.data.get("status")
        location = request.data.get("location", "")
        description = request.data.get("description", "")
        if new_status and new_status in Shipment.Status.values:
            before = shp.status
            shp.status = new_status
            shp.save(update_fields=["status", "updated_at"])
            if location or description:
                ShipmentEvent.objects.create(
                    shipment=shp,
                    location_name=location or str(new_status),
                    event_description=description or f"Status changed from {before} to {new_status}",
                )
            log_event(
                "shipments.status_changed",
                entity=shp,
                summary=f"Shipment {shp.shipment_number} status changed to {new_status}",
                sensitive=True,
            )
        # Re-fetch with fresh prefetched events
        fresh = Shipment.objects.prefetch_related("documents", "events").get(pk=shp.pk)
        return Response(ShipmentSerializer(fresh).data, status=status.HTTP_200_OK)


class ShipmentDocumentViewSet(viewsets.ModelViewSet):
    queryset = ShipmentDocument.objects.select_related("shipment")
    serializer_class = ShipmentDocumentSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "shipments.shipment.view",
        "retrieve": "shipments.shipment.view",
        "create": "shipments.shipment.edit",
        "update": "shipments.shipment.edit",
        "partial_update": "shipments.shipment.edit",
        "destroy": "shipments.shipment.manage",
    }


class ShipmentEventViewSet(viewsets.ModelViewSet):
    queryset = ShipmentEvent.objects.select_related("shipment")
    serializer_class = ShipmentEventSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "shipments.shipment.view",
        "retrieve": "shipments.shipment.view",
        "create": "shipments.shipment.edit",
        "update": "shipments.shipment.edit",
        "partial_update": "shipments.shipment.edit",
        "destroy": "shipments.shipment.manage",
    }
