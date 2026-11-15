from rest_framework.routers import DefaultRouter

from apps.documents_ai.views import DocumentViewSet, ExtractionJobViewSet

router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"extractions", ExtractionJobViewSet, basename="extraction-job")

urlpatterns = router.urls
