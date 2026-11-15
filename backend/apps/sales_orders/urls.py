from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("deals", views.DealViewSet, basename="deal")
router.register("sales-orders", views.SalesOrderViewSet, basename="sales-order")
router.register("sales-order-lines", views.SalesOrderLineViewSet, basename="sales-order-line")

urlpatterns = router.urls
