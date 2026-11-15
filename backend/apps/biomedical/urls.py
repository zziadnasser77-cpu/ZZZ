from rest_framework.routers import DefaultRouter

from apps.biomedical.views import (
    InstallationProtocolViewSet,
    ServiceTicketViewSet,
    SparePartRequestViewSet,
    WarrantyContractViewSet,
)

router = DefaultRouter()
router.register(r"protocols", InstallationProtocolViewSet, basename="installation-protocol")
router.register(r"warranties", WarrantyContractViewSet, basename="warranty-contract")
router.register(r"tickets", ServiceTicketViewSet, basename="service-ticket")
router.register(r"spare-parts", SparePartRequestViewSet, basename="spare-part-request")

urlpatterns = router.urls
