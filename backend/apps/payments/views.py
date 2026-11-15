from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.exceptions import BusinessRuleViolation
from apps.identity_access.permissions import HasPermission
from apps.payments.models import (
    BankAccount,
    CustomerInvoice,
    Payment,
    PaymentAllocation,
    SupplierBill,
)
from apps.payments.serializers import (
    BankAccountSerializer,
    CustomerInvoiceSerializer,
    PaymentAllocationSerializer,
    PaymentSerializer,
    SupplierBillSerializer,
)
from apps.payments.services import (
    allocate_payment,
    post_customer_invoice,
    post_payment,
    post_supplier_bill,
)


class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.select_related("currency", "gl_account").all()
    serializer_class = BankAccountSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "payments.bank_account.view",
        "retrieve": "payments.bank_account.view",
        "create": "payments.bank_account.create",
        "update": "payments.bank_account.edit",
        "partial_update": "payments.bank_account.edit",
        "destroy": "payments.bank_account.manage",
    }


class CustomerInvoiceViewSet(viewsets.ModelViewSet):
    queryset = (
        CustomerInvoice.objects.select_related(
            "customer", "currency", "sales_order", "deal", "gl_entry", "created_by"
        )
        .prefetch_related("lines__model")
        .all()
    )
    serializer_class = CustomerInvoiceSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "payments.invoice.view",
        "retrieve": "payments.invoice.view",
        "create": "payments.invoice.create",
        "update": "payments.invoice.edit",
        "partial_update": "payments.invoice.edit",
        "destroy": "payments.invoice.cancel",
        "post_invoice": "payments.invoice.post",
    }
    filterset_fields = ["status", "customer", "currency", "sales_order", "deal"]
    search_fields = ["invoice_number", "customer__legal_name_ar", "customer__code"]

    @action(detail=True, methods=["post"])
    def post_invoice(self, request, pk=None):
        invoice = self.get_object()
        post_customer_invoice(invoice, user=request.user)
        invoice.refresh_from_db()
        return Response(CustomerInvoiceSerializer(invoice, context={"request": request}).data)


class SupplierBillViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierBill.objects.select_related(
            "supplier", "currency", "supplier_order", "gl_entry", "created_by"
        )
        .prefetch_related("lines")
        .all()
    )
    serializer_class = SupplierBillSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "payments.bill.view",
        "retrieve": "payments.bill.view",
        "create": "payments.bill.create",
        "update": "payments.bill.edit",
        "partial_update": "payments.bill.edit",
        "destroy": "payments.bill.cancel",
        "post_bill": "payments.bill.post",
    }
    filterset_fields = ["status", "supplier", "currency", "supplier_order"]
    search_fields = ["bill_number", "supplier__name_ar", "supplier__code"]

    @action(detail=True, methods=["post"])
    def post_bill(self, request, pk=None):
        bill = self.get_object()
        post_supplier_bill(bill, user=request.user)
        bill.refresh_from_db()
        return Response(SupplierBillSerializer(bill, context={"request": request}).data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = (
        Payment.objects.select_related(
            "customer", "supplier", "bank_account", "currency", "gl_entry", "created_by"
        )
        .prefetch_related("allocations__invoice", "allocations__bill")
        .all()
    )
    serializer_class = PaymentSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "payments.payment.view",
        "retrieve": "payments.payment.view",
        "create": "payments.payment.create",
        "update": "payments.payment.edit",
        "partial_update": "payments.payment.edit",
        "destroy": "payments.payment.cancel",
        "post_payment": "payments.payment.post",
        "allocate": "payments.payment.edit",
    }
    filterset_fields = ["status", "payment_type", "customer", "supplier", "bank_account", "currency"]
    search_fields = ["payment_number", "reference_number", "customer__legal_name_ar", "supplier__name_ar"]

    @action(detail=True, methods=["post"])
    def post_payment(self, request, pk=None):
        payment = self.get_object()
        post_payment(payment, user=request.user)
        payment.refresh_from_db()
        return Response(PaymentSerializer(payment, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        payment = self.get_object()
        amount_str = request.data.get("amount")
        if not amount_str:
            raise BusinessRuleViolation("يجب تحديد مبلغ التوزيع.")
        amount = Decimal(str(amount_str))

        invoice_id = request.data.get("invoice_id")
        bill_id = request.data.get("bill_id")

        invoice = CustomerInvoice.objects.get(pk=invoice_id) if invoice_id else None
        bill = SupplierBill.objects.get(pk=bill_id) if bill_id else None

        allocation = allocate_payment(payment, invoice=invoice, bill=bill, amount=amount, user=request.user)
        return Response(PaymentAllocationSerializer(allocation).data, status=status.HTTP_201_CREATED)


class PaymentAllocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaymentAllocation.objects.select_related("payment", "invoice", "bill").all()
    serializer_class = PaymentAllocationSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "payments.payment.view",
        "retrieve": "payments.payment.view",
    }
    filterset_fields = ["payment", "invoice", "bill"]
