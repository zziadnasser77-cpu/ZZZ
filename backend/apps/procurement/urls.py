from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("supplier-orders", views.SupplierOrderViewSet, basename="supplier-order")
router.register("supplier-order-lines", views.SupplierOrderLineViewSet, basename="supplier-order-line")

urlpatterns = router.urls
