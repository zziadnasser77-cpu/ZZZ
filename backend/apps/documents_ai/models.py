from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.organization_settings.models import next_document_number


class DocumentType(models.TextChoices):
    PROFORMA_INVOICE = "PROFORMA_INVOICE", _("فاتورة مبدئية PI (الصين)")
    COMMERCIAL_INVOICE = "COMMERCIAL_INVOICE", _("فاتورة تجارية CI")
    PACKING_LIST = "PACKING_LIST", _("كشف التعبئة والتغليف PL")
    BILL_OF_LADING = "BILL_OF_LADING", _("بوليصة الشحن B/L")
    CERTIFICATE_OF_ORIGIN = "CERTIFICATE_OF_ORIGIN", _("شهادة المنشأ COO")
    CATALOG_BROCHURE = "CATALOG_BROCHURE", _("كتالوج ومواصفات الموديل")
    SERVICE_MANUAL = "SERVICE_MANUAL", _("دليل الصيانة والتشغيل")
    WARRANTY_CERTIFICATE = "WARRANTY_CERTIFICATE", _("شهادة الضمان المصنعي")
    CUSTOMS_DECLARATION = "CUSTOMS_DECLARATION", _("بيان جمركي محلي")
    OTHER = "OTHER", _("أخرى")


class Document(BaseModel):
    document_number = models.CharField(max_length=32, unique=True, blank=True)
    title = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    file = models.FileField(upload_to="documents/%Y/%m/", null=True, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    file_hash = models.CharField(max_length=64, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=10, default="en")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("مستند مؤرشف")
        verbose_name_plural = _("أرشيف المستندات")

    def __str__(self):
        return f"{self.document_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.document_number:
            self.document_number = next_document_number("DOCUMENT", prefix="DOC")
        super().save(*args, **kwargs)


class ExtractionJob(BaseModel):
    class TargetEntityType(models.TextChoices):
        PRICE_LIST = "PRICE_LIST", _("قائمة أسعار مورد")
        PRODUCT_SPECS = "PRODUCT_SPECS", _("مواصفات موديل طبي")
        SPARE_PARTS = "SPARE_PARTS", _("قائمة قطع غيار")
        SHIPMENT_DOC = "SHIPMENT_DOC", _("بيانات بوليصة وشحنة")
        INVOICE = "INVOICE", _("فاتورة مورد ومطابقة")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("قيد الانتظار")
        PROCESSING = "PROCESSING", _("قيد المعالجة واستخراج OCR/AI")
        AWAITING_REVIEW = "AWAITING_REVIEW", _("بانتظار المراجعة والاعتماد البشري")
        APPROVED = "APPROVED", _("معتمد بشرياً")
        REJECTED = "REJECTED", _("مرفوض")
        FAILED = "FAILED", _("فشل الاستخراج")

    job_number = models.CharField(max_length=32, unique=True, blank=True)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="extraction_jobs")
    target_entity_type = models.CharField(max_length=30, choices=TargetEntityType.choices)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=50, default="GEMINI_FLASH_GATEWAY")
    raw_response = models.JSONField(default=dict, blank=True)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.950"))
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_extractions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("مهمة استخراج ذكاء اصطناعي")
        verbose_name_plural = _("مهام استخراج الذكاء الاصطناعي")

    def __str__(self):
        return f"{self.job_number} ({self.get_status_display()}) - {self.document.title}"

    def save(self, *args, **kwargs):
        if not self.job_number:
            self.job_number = next_document_number("EXTRACTION_JOB", prefix="EXT")
        super().save(*args, **kwargs)


class ExtractionField(BaseModel):
    job = models.ForeignKey(ExtractionJob, on_delete=models.CASCADE, related_name="fields")
    field_key = models.CharField(max_length=100)
    extracted_value = models.TextField()
    corrected_value = models.TextField(blank=True)
    page_number = models.PositiveIntegerField(default=1)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.950"))
    is_approved = models.BooleanField(default=False)
    is_unknown_or_missing = models.BooleanField(default=False)

    class Meta:
        ordering = ["page_number", "field_key"]
        verbose_name = _("حقل مستخرج")
        verbose_name_plural = _("الحقول المستخرجة")

    def __str__(self):
        val = self.corrected_value or self.extracted_value
        return f"{self.field_key}: {val} ({'معتمد' if self.is_approved else 'غير معتمد'})"
