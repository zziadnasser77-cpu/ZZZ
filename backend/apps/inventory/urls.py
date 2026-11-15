from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("locations", views.LocationViewSet, basename="location")
router.register("serial-assets", views.SerialAssetViewSet, basename="serial-asset")
router.register("ownership-records", views.OwnershipRecordViewSet, basename="ownership-record")
router.register("custody-records", views.CustodyRecordViewSet, basename="custody-record")
router.register("stock-movements", views.StockMovementViewSet, basename="stock-movement")
router.register("stock-counts", views.StockCountViewSet, basename="stock-count")
router.register("stock-count-items", views.StockCountItemViewSet, basename="stock-count-item")

urlpatterns = router.urls
