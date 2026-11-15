from rest_framework.routers import DefaultRouter

from apps.accounting.views import (
    AccountViewSet,
    CurrencyViewSet,
    ExchangeRateViewSet,
    JournalEntryViewSet,
    JournalLineViewSet,
)

router = DefaultRouter()
router.register(r"currencies", CurrencyViewSet, basename="currency")
router.register(r"exchange-rates", ExchangeRateViewSet, basename="exchange-rate")
router.register(r"accounts", AccountViewSet, basename="account")
router.register(r"entries", JournalEntryViewSet, basename="journal-entry")
router.register(r"lines", JournalLineViewSet, basename="journal-line")

urlpatterns = router.urls
