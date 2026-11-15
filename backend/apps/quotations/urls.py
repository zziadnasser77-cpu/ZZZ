from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("quotations", views.QuotationViewSet, basename="quotation")
router.register("quotation-versions", views.QuotationVersionViewSet, basename="quotation-version")
router.register("quotation-lines", views.QuotationLineViewSet, basename="quotation-line")

urlpatterns = router.urls
