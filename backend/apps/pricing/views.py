from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.identity_access.permissions import HasPermission

from .models import PriceList, PriceListItem
from .serializers import PriceListItemSerializer, PriceListSerializer


class PriceListViewSet(viewsets.ModelViewSet):
    queryset = PriceList.objects.prefetch_related("items__model__product")
    serializer_class = PriceListSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "pricing.pricelist.view",
        "retrieve": "pricing.pricelist.view",
        "create": "pricing.pricelist.create",
        "update": "pricing.pricelist.edit",
        "partial_update": "pricing.pricelist.edit",
        "destroy": "pricing.pricelist.manage",
        "activate": "pricing.pricelist.approve",
    }
    search_fields = ["code", "name_ar", "name_en", "description"]
    filterset_fields = ["currency", "status", "is_active", "is_default"]
    ordering_fields = ["effective_from", "code", "created_at"]

    def perform_create(self, serializer):
        pl = serializer.save()
        log_event("pricing.pricelist_created", entity=pl, summary=f"PriceList {pl.code}")

    def perform_update(self, serializer):
        pl = serializer.save()
        log_event("pricing.pricelist_updated", entity=pl, summary=f"PriceList {pl.code} updated")

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        if not request.user.has_perm_code("pricing.pricelist.approve"):
            raise PermissionDenied("Activating price lists requires pricing.pricelist.approve permission.")
        pl = self.get_object()
        pl.status = PriceList.Status.ACTIVE
        pl.is_active = True
        pl.save(update_fields=["status", "is_active", "updated_at"])
        log_event(
            "pricing.pricelist_activated", entity=pl, summary=f"PriceList {pl.code} activated", sensitive=True
        )
        return Response(PriceListSerializer(pl, context={"request": request}).data, status=status.HTTP_200_OK)


class PriceListItemViewSet(viewsets.ModelViewSet):
    queryset = PriceListItem.objects.select_related("price_list", "model__product")
    serializer_class = PriceListItemSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "pricing.item.view",
        "retrieve": "pricing.item.view",
        "create": "pricing.item.create",
        "update": "pricing.item.edit",
        "partial_update": "pricing.item.edit",
        "destroy": "pricing.item.manage",
    }
    search_fields = ["model__model_code", "model__model_name", "model__sku", "price_list__code"]
    filterset_fields = ["price_list", "model"]

    def perform_create(self, serializer):
        item = serializer.save()
        log_event(
            "pricing.item_created",
            entity=item,
            summary=f"Price for {item.model.sku} in {item.price_list.code} set to {item.base_price}",
            sensitive=True,
        )

    def perform_update(self, serializer):
        before_base = serializer.instance.base_price
        before_min = serializer.instance.min_price
        item = serializer.save()
        changes = {
            "base_price": {"before": str(before_base), "after": str(item.base_price)},
            "min_price": {"before": str(before_min), "after": str(item.min_price)},
        }
        log_event(
            "pricing.item_updated",
            entity=item,
            summary=f"Price for {item.model.sku} in {item.price_list.code} updated",
            changes=changes,
            sensitive=True,
        )
