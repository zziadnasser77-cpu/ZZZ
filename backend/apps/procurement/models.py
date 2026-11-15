from django.db import models

from apps.catalog.models import ProductModel
from apps.common.models import BaseModel
from apps.organization_settings.models import next_document_number
from apps.sales_orders.models import Deal


class Supplier(BaseModel):
    """Supplier / Principal profile (Chinese partner company, accessories suppliers). Spec §5.6, §7."""

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    country = models.CharField(max_length=60, default="China")
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.CharField(max_length=200, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    payment_terms = models.TextField(blank=True, help_text="e.g. 30% advance deposit, 70% before shipment")
    is_primary_partner = models.BooleanField(default=False, help_text="الشركة الصينية الشريك الرئيسي")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name_ar}"


class SupplierOrder(BaseModel):
    """Purchase Order to Chinese supplier/partner with PI reference and pre-shipment tracking. Spec §5.6, ADR-022."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        PENDING_APPROVAL = "PENDING_APPROVAL", "بانتظار الاعتماد الداخلي"
        APPROVED = "APPROVED", "معتمد للشراء"
        SENT_TO_SUPPLIER = "SENT_TO_SUPPLIER", "مرسل للمصنع / الشريك الصيني"
        CONFIRMED_BY_SUPPLIER = "CONFIRMED_BY_SUPPLIER", "مؤكد من المورد (PI Issued)"
        IN_PRODUCTION = "IN_PRODUCTION", "قيد التصنيع والتجهيز"
        READY_FOR_DISPATCH = "READY_FOR_DISPATCH", "جاهز للشحن وفحص ما قبل الشحن"
        SHIPPED = "SHIPPED", "مشحون"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "استلام جزئي"
        RECEIVED = "RECEIVED", "مستلم بالكامل"
        CANCELLED = "CANCELLED", "ملغي"

    class ProcurementModel(models.TextChoices):
        DIRECT_STOCK = "DIRECT_STOCK", "شراء مخزون مملوك"
        DEAL_BACK_TO_BACK = "DEAL_BACK_TO_BACK", "توريد مخصص لصفقة عميل"
        AGENCY_COORDINATION = "AGENCY_COORDINATION", "تنسيق وكالة (لا يمثل شراء مخزون)"

    order_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="orders")
    deal = models.ForeignKey(
        Deal,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supplier_orders",
        help_text="الصفقة المرتبطة إن وجدت",
    )
    procurement_model = models.CharField(
        max_length=30,
        choices=ProcurementModel.choices,
        default=ProcurementModel.DEAL_BACK_TO_BACK,
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    currency = models.CharField(max_length=3, default="USD")
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)

    # Supplier confirmation & shipment tracking (Spec §5.6, ADR-022)
    supplier_pi_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="رقم الفاتورة المبدئية Proforma Invoice من المصنع الصيني",
    )
    estimated_dispatch_date = models.DateField(null=True, blank=True)
    shipping_port = models.CharField(max_length=100, blank=True, help_text="e.g. Shenzhen, Shanghai")
    destination_port = models.CharField(max_length=100, blank=True, help_text="e.g. Aden, Sanaa Cargo")
    freight_payer = models.CharField(max_length=100, blank=True, help_text="الجهة المتحملة لتكاليف الشحن")
    customs_payer = models.CharField(max_length=100, blank=True, help_text="الجهة المتحملة للتخليص الجمركي")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["supplier", "status"]),
            models.Index(fields=["deal", "status"]),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.supplier.name_ar})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = next_document_number("supplier_order", prefix="PO")
        super().save(*args, **kwargs)


class SupplierOrderLine(BaseModel):
    """Line item in a Supplier Purchase Order."""

    order = models.ForeignKey(SupplierOrder, on_delete=models.CASCADE, related_name="lines")
    model = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="+")
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2)
    total_cost = models.DecimalField(max_digits=18, decimal_places=2)
    received_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.model.model_name} x {self.quantity}"
