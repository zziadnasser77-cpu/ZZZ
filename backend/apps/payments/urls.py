from rest_framework.routers import DefaultRouter

from apps.payments.views import (
    BankAccountViewSet,
    CustomerInvoiceViewSet,
    PaymentAllocationViewSet,
    PaymentViewSet,
    SupplierBillViewSet,
)

router = DefaultRouter()
router.register(r"bank-accounts", BankAccountViewSet, basename="bank-account")
router.register(r"invoices", CustomerInvoiceViewSet, basename="customer-invoice")
router.register(r"bills", SupplierBillViewSet, basename="supplier-bill")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"allocations", PaymentAllocationViewSet, basename="payment-allocation")

urlpatterns = router.urls
