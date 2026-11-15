from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("price-lists", views.PriceListViewSet, basename="price-list")
router.register("price-list-items", views.PriceListItemViewSet, basename="price-list-item")

urlpatterns = router.urls
