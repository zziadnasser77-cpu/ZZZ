from django.conf import settings
from django.db import models

from apps.catalog.models import ProductModel
from apps.common.models import BaseModel
from apps.crm.models import Customer, Opportunity
from apps.organization_settings.models import next_document_number


class CommercialModel(models.TextChoices):
    DIRECT_SALE = "DIRECT_SALE", "بيع مباشر (موزع)"
    AGENCY = "AGENCY", "وكالة وعمولة (الشريك الصيني)"
    TENDER = "TENDER", "مناقصة رسمية"
    OTHER = "OTHER", "أخرى"


class Quotation(BaseModel):
    """Quotation container tracking versions and commercial model. Spec §5.4, §7."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        PENDING_APPROVAL = "PENDING_APPROVAL", "بانتظار الاعتماد"
        APPROVED = "APPROVED", "معتمد"
        SENT = "SENT", "مرسل للعميل"
        ACCEPTED = "ACCEPTED", "مقبول من العميل"
        REJECTED = "REJECTED", "مرفوض"
        EXPIRED = "EXPIRED", "منتهي الصلاحية"
        CANCELLED = "CANCELLED", "ملغي"

    quotation_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    title = models.CharField(max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="quotations")
    opportunity = models.ForeignKey(
        Opportunity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotations",
    )
    commercial_model = models.CharField(
        max_length=30,
        choices=CommercialModel.choices,
        default=CommercialModel.DIRECT_SALE,
    )
    currency = models.CharField(max_length=3, default="USD")
    current_version_number = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
        ]

    def __str__(self):
        return f"{self.quotation_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            self.quotation_number = next_document_number("quotation", prefix="QT")
        super().save(*args, **kwargs)


class QuotationVersion(BaseModel):
    """Immutable version snapshot of a quotation. Spec §5.4, ADR-021."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        PENDING_APPROVAL = "PENDING_APPROVAL", "بانتظار الاعتماد"
        APPROVED = "APPROVED", "معتمد"
        SENT = "SENT", "مرسل للعميل"
        ACCEPTED = "ACCEPTED", "مقبول"
        REJECTED = "REJECTED", "مرفوض"
        SUPERSEDED = "SUPERSEDED", "مستبدل بإصدار أحدث"

    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)

    valid_until = models.DateField(null=True, blank=True)
    payment_terms = models.TextField(blank=True, help_text="شروط الدفع والدفعات المقدمة")
    delivery_terms = models.TextField(blank=True, help_text="شروط ومكان التسليم والتركيب")
    notes = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)

    requires_approval = models.BooleanField(default=False)
    approval_reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Immutable frozen copy of customer, models, prices, terms at time of approval/issuance
    snapshot = models.JSONField(null=True, blank=True, help_text="تجميد البيانات وقت الإصدار")

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(fields=["quotation", "version_number"], name="uniq_quotation_version")
        ]

    def __str__(self):
        return f"{self.quotation.quotation_number} (v{self.version_number})"


class QuotationLine(BaseModel):
    """Line item in a specific quotation version."""

    version = models.ForeignKey(QuotationVersion, on_delete=models.CASCADE, related_name="lines")
    model = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="+")
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=18, decimal_places=2)
    warranty_months = models.PositiveSmallIntegerField(default=12)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.model.model_name} x {self.quantity}"
