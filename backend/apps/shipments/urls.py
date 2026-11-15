from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("shipments", views.ShipmentViewSet, basename="shipment")
router.register("shipment-documents", views.ShipmentDocumentViewSet, basename="shipment-document")
router.register("shipment-events", views.ShipmentEventViewSet, basename="shipment-event")

urlpatterns = router.urls
