from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("manufacturers", views.ManufacturerViewSet, basename="manufacturer")
router.register("products", views.ProductViewSet, basename="product")
router.register("models", views.ProductModelViewSet, basename="product-model")

urlpatterns = router.urls
