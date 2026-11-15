from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("contacts", views.ContactViewSet, basename="contact")
router.register("opportunities", views.OpportunityViewSet, basename="opportunity")
router.register("activities", views.ActivityViewSet, basename="activity")

urlpatterns = router.urls
