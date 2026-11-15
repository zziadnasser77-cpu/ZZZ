from django.db import models

from apps.catalog.models import ProductModel
from apps.common.models import BaseModel
from apps.crm.models import Customer
from apps.organization_settings.models import next_document_number
from apps.quotations.models import CommercialModel, Quotation


class Deal(BaseModel):
    """Deal container enforcing Commercial Model, Legal Seller, and Invoicing rules. Spec §5.5, §7.1."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        PENDING_APPROVAL = "PENDING_APPROVAL", "بانتظار الاعتماد"
        APPROVED = "APPROVED", "معتمدة"
        CONFIRMED = "CONFIRMED", "مؤكدة"
        IN_PROGRESS = "IN_PROGRESS", "قيد التنفيذ والتوريد"
        PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED", "تسليم جزئي"
        DELIVERED = "DELIVERED", "مكتملة التسليم"
        CLOSED = "CLOSED", "مغلقة ومحصلة"
        CANCELLED = "CANCELLED", "ملغاة"

    deal_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    title = models.CharField(max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="deals")
    quotation = models.ForeignKey(
        Quotation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deals",
    )

    # Core non-negotiable legal/commercial fields (Spec §1.1, §7.1)
    commercial_model = models.CharField(
        max_length=30,
        choices=CommercialModel.choices,
        default=CommercialModel.DIRECT_SALE,
        help_text="النموذج التجاري: بيع مباشر، وكالة، مناقصة",
    )
    seller_of_record = models.CharField(
        max_length=200,
        help_text="البائع القانوني (الشركة المحلية أو الشريك الصيني)",
    )
    invoice_issuer = models.CharField(
        max_length=200,
        help_text="الجهة المصدرة للفاتورة للعميل",
    )
    payment_recipient = models.CharField(
        max_length=200,
        help_text="الجهة المستلمة للأموال (الحساب البنكي / الصندوق)",
    )

    currency = models.CharField(max_length=3, default="USD")
    total_value = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)

    # Agency specific commission tracking (Spec §6.3)
    commission_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True)
    expected_commission_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0.00, blank=True
    )

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["commercial_model", "status"]),
        ]

    def __str__(self):
        return f"{self.deal_number} - {self.title} ({self.commercial_model})"

    def save(self, *args, **kwargs):
        if not self.deal_number:
            self.deal_number = next_document_number("deal", prefix="DEAL")
        if not self.seller_of_record:
            self.seller_of_record = (
                "SMSES Local Partner"
                if self.commercial_model == CommercialModel.DIRECT_SALE
                else "Chinese Partner Company"
            )
        if not self.invoice_issuer:
            self.invoice_issuer = self.seller_of_record
        if not self.payment_recipient:
            self.payment_recipient = "SMSES Local Partner"
        super().save(*args, **kwargs)


class SalesOrder(BaseModel):
    """Execution Sales Order linked to a Deal. Spec §5.5, §7."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        CONFIRMED = "CONFIRMED", "مؤكد"
        PROCESSING = "PROCESSING", "قيد التجهيز والتوريد"
        SHIPPED = "SHIPPED", "مشحون"
        DELIVERED = "DELIVERED", "تم التسليم للعميل"
        CANCELLED = "CANCELLED", "ملغي"

    order_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    deal = models.ForeignKey(Deal, on_delete=models.PROTECT, related_name="sales_orders")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders")

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    currency = models.CharField(max_length=3, default="USD")
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)

    delivery_terms = models.TextField(blank=True)
    payment_terms = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["deal", "status"]),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.customer.legal_name_ar})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = next_document_number("sales_order", prefix="SO")
        super().save(*args, **kwargs)


class SalesOrderLine(BaseModel):
    """Line item in a Sales Order."""

    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    model = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="+")
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    total_price = models.DecimalField(max_digits=18, decimal_places=2)
    delivered_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.model.model_name} x {self.quantity}"
