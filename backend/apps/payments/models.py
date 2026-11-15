from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounting.models import Account, Currency, JournalEntry
from apps.catalog.models import ProductModel
from apps.common.exceptions import BusinessRuleViolation
from apps.common.models import BaseModel
from apps.crm.models import Customer
from apps.organization_settings.models import next_document_number
from apps.procurement.models import Supplier, SupplierOrder
from apps.sales_orders.models import Deal, SalesOrder


class BankAccountType(models.TextChoices):
    CASH_REGISTER = "CASH_REGISTER", _("صندوق نقدي - Cash Register")
    BANK_ACCOUNT = "BANK_ACCOUNT", _("حساب بنكي - Bank Account")


class BankAccount(BaseModel):
    account_type = models.CharField(
        max_length=20,
        choices=BankAccountType.choices,
        default=BankAccountType.BANK_ACCOUNT,
    )
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    iban = models.CharField(max_length=50, blank=True)
    swift_bic = models.CharField(max_length=20, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="bank_accounts")
    gl_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_accounts",
    )
    opening_balance = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    current_balance = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name_ar"]
        verbose_name = _("حساب مصرفي / صندوق")
        verbose_name_plural = _("الحسابات المصرفية والصناديق")

    def __str__(self):
        return f"{self.name_ar} ({self.currency.code})"


class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", _("مسودة - Draft")
    APPROVED = "APPROVED", _("معتمد - Approved")
    POSTED = "POSTED", _("مرحل - Posted")
    PARTIALLY_PAID = "PARTIALLY_PAID", _("مدفوع جزئياً - Partially Paid")
    PAID = "PAID", _("مدفوع بالكامل - Paid")
    CANCELLED = "CANCELLED", _("ملغي - Cancelled")


class CustomerInvoice(BaseModel):
    invoice_number = models.CharField(max_length=32, unique=True, blank=True)
    sales_order = models.ForeignKey(
        SalesOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    deal = models.ForeignKey(Deal, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="customer_invoices")
    exchange_rate = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal("1.000000"))
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    gl_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customer_invoices",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-invoice_date", "-created_at"]
        verbose_name = _("فاتورة عميل")
        verbose_name_plural = _("فواتير العملاء")

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.legal_name_ar}"

    @property
    def remaining_amount(self) -> Decimal:
        return self.total_amount - self.paid_amount

    def delete(self, *args, **kwargs):
        if self.status in (InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID):
            raise BusinessRuleViolation(_("لا يمكن حذف فاتورة مرحلة أو مدفوعة."))
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = next_document_number("CUSTOMER_INVOICE", prefix="INV")
        super().save(*args, **kwargs)


class CustomerInvoiceLine(BaseModel):
    invoice = models.ForeignKey(CustomerInvoice, on_delete=models.CASCADE, related_name="lines")
    model = models.ForeignKey(ProductModel, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=16, decimal_places=2)
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("سطر فاتورة عميل")
        verbose_name_plural = _("أسطر فواتير العملاء")

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class SupplierBillStatus(models.TextChoices):
    DRAFT = "DRAFT", _("مسودة - Draft")
    APPROVED = "APPROVED", _("معتمد - Approved")
    POSTED = "POSTED", _("مرحل - Posted")
    PARTIALLY_PAID = "PARTIALLY_PAID", _("مدفوع جزئياً - Partially Paid")
    PAID = "PAID", _("مدفوع بالكامل - Paid")
    CANCELLED = "CANCELLED", _("ملغي - Cancelled")


class SupplierBill(BaseModel):
    bill_number = models.CharField(max_length=32, unique=True, blank=True)
    supplier_order = models.ForeignKey(
        SupplierOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bills",
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="bills")
    bill_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="supplier_bills")
    exchange_rate = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal("1.000000"))
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=20, choices=SupplierBillStatus.choices, default=SupplierBillStatus.DRAFT
    )
    gl_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supplier_bills",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-bill_date", "-created_at"]
        verbose_name = _("فاتورة مورد")
        verbose_name_plural = _("فواتير الموردين")

    def __str__(self):
        return f"{self.bill_number} - {self.supplier.name_ar}"

    @property
    def remaining_amount(self) -> Decimal:
        return self.total_amount - self.paid_amount

    def delete(self, *args, **kwargs):
        if self.status in (
            SupplierBillStatus.POSTED,
            SupplierBillStatus.PARTIALLY_PAID,
            SupplierBillStatus.PAID,
        ):
            raise BusinessRuleViolation(_("لا يمكن حذف فاتورة مورد مرحلة أو مدفوعة."))
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.bill_number = next_document_number("SUPPLIER_BILL", prefix="BILL")
        super().save(*args, **kwargs)


class SupplierBillLine(BaseModel):
    bill = models.ForeignKey(SupplierBill, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=16, decimal_places=2)
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class PaymentType(models.TextChoices):
    CUSTOMER_RECEIPT = "CUSTOMER_RECEIPT", _("سند قبض عميل - Customer Receipt")
    SUPPLIER_DISBURSEMENT = "SUPPLIER_DISBURSEMENT", _("سند صرف مورد - Supplier Disbursement")


class PaymentMethod(models.TextChoices):
    CASH = "CASH", _("نقداً - Cash")
    BANK_TRANSFER = "BANK_TRANSFER", _("تحويل بنكي - Bank Transfer")
    CHECK = "CHECK", _("شيك - Check")
    OTHER = "OTHER", _("أخرى - Other")


class PaymentStatus(models.TextChoices):
    DRAFT = "DRAFT", _("مسودة - Draft")
    POSTED = "POSTED", _("مرحل - Posted")
    VOID = "VOID", _("ملغي - Void")


class Payment(BaseModel):
    payment_number = models.CharField(max_length=32, unique=True, blank=True)
    payment_type = models.CharField(max_length=30, choices=PaymentType.choices)
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="payments")
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    reference_number = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="payments")
    exchange_rate = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal("1.000000"))
    base_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    allocated_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    unallocated_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.DRAFT)
    gl_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        verbose_name = _("سند مالي")
        verbose_name_plural = _("سندات القبض والصرف")

    def __str__(self):
        return (
            f"{self.payment_number} ({self.get_payment_type_display()}): {self.amount} {self.currency.code}"
        )

    def delete(self, *args, **kwargs):
        if self.status == PaymentStatus.POSTED:
            raise BusinessRuleViolation(_("لا يمكن حذف سند مالي مرحل."))
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = next_document_number("PAYMENT", prefix="PAY")
        if self.base_amount == Decimal("0.00") and self.amount > Decimal("0.00"):
            self.base_amount = round(self.amount * self.exchange_rate, 2)
        if (
            self.unallocated_amount == Decimal("0.00")
            and self.allocated_amount == Decimal("0.00")
            and self.amount > Decimal("0.00")
        ):
            self.unallocated_amount = self.amount
        super().save(*args, **kwargs)


class PaymentAllocation(BaseModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(
        CustomerInvoice, null=True, blank=True, on_delete=models.CASCADE, related_name="allocations"
    )
    bill = models.ForeignKey(
        SupplierBill, null=True, blank=True, on_delete=models.CASCADE, related_name="allocations"
    )
    allocated_amount = models.DecimalField(max_digits=16, decimal_places=2)
    allocated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-allocated_at"]
        verbose_name = _("توزيع دفعة")
        verbose_name_plural = _("توزيعات الدفعات")

    def __str__(self):
        return f"{self.payment.payment_number} -> {self.allocated_amount}"
