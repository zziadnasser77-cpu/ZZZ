from django.db import models

from apps.common.models import BaseModel
from apps.organization_settings.models import next_document_number
from apps.procurement.models import SupplierOrder
from apps.sales_orders.models import SalesOrder


class Shipment(BaseModel):
    """Shipment tracker connecting Supplier Orders or Customer Deliveries. Spec §5.7, §7."""

    class ShippingMethod(models.TextChoices):
        SEA_FREIGHT = "SEA_FREIGHT", "شحن بحري (حاويات)"
        AIR_FREIGHT = "AIR_FREIGHT", "شحن جوي سريع"
        LAND_TRANSIT = "LAND_TRANSIT", "نقل بري محلي"

    class Status(models.TextChoices):
        PREPARING = "PREPARING", "قيد التجهيز والتغليف"
        DISPATCHED = "DISPATCHED", "تم الانطلاق من بلد المنشأ"
        IN_TRANSIT = "IN_TRANSIT", "في عرض البحر / العبور الجوي"
        PORT_ARRIVAL = "PORT_ARRIVAL", "وصلت ميناء/مطار الوصول"
        CUSTOMS_CLEARANCE = "CUSTOMS_CLEARANCE", "تحت إجراءات التخليص الجمركي"
        RECEIVED_LOCALLY = "RECEIVED_LOCALLY", "تم الاستلام في المستودع المحلي"
        DELIVERED_TO_CUSTOMER = "DELIVERED_TO_CUSTOMER", "تم التسليم للعميل"
        CANCELLED = "CANCELLED", "ملغاة"

    shipment_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    supplier_order = models.ForeignKey(
        SupplierOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shipments",
    )
    sales_order = models.ForeignKey(
        SalesOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shipments",
    )

    carrier_name = models.CharField(max_length=150, help_text="شركة الملاحة أو الشحن")
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    shipping_method = models.CharField(
        max_length=20,
        choices=ShippingMethod.choices,
        default=ShippingMethod.SEA_FREIGHT,
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PREPARING, db_index=True)

    origin_port = models.CharField(max_length=100, default="Shenzhen Port, China")
    destination_port = models.CharField(max_length=100, default="Aden Port, Yemen")

    estimated_departure = models.DateField(null=True, blank=True)
    actual_departure = models.DateField(null=True, blank=True)
    estimated_arrival = models.DateField(null=True, blank=True)
    actual_arrival = models.DateField(null=True, blank=True)

    freight_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    customs_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "tracking_number"]),
        ]

    def __str__(self):
        return f"{self.shipment_number} - {self.carrier_name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.shipment_number:
            self.shipment_number = next_document_number("shipment", prefix="SHP")
        super().save(*args, **kwargs)


class ShipmentDocument(BaseModel):
    """Shipping document (Bill of Lading, Packing List, COO, Inspection). Spec §5.7."""

    class DocType(models.TextChoices):
        BILL_OF_LADING = "BILL_OF_LADING", "بوليصة الشحن (B/L)"
        PACKING_LIST = "PACKING_LIST", "كشف التعبئة (Packing List)"
        COMMERCIAL_INVOICE = "COMMERCIAL_INVOICE", "الفاتورة التجارية النهائية"
        CERTIFICATE_OF_ORIGIN = "CERTIFICATE_OF_ORIGIN", "شهادة المنشأ (COO)"
        INSPECTION_CERTIFICATE = "INSPECTION_CERTIFICATE", "شهادة فحص ما قبل الشحن"
        CUSTOMS_DECLARATION = "CUSTOMS_DECLARATION", "بيان جمركي محلي"
        OTHER = "OTHER", "أخرى"

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=30, choices=DocType.choices, default=DocType.BILL_OF_LADING)
    document_number = models.CharField(max_length=100, blank=True)
    file_url = models.CharField(max_length=300, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.doc_type} - {self.document_number}"


class ShipmentEvent(BaseModel):
    """Milestone event in shipment journey. Spec §5.7."""

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="events")
    location_name = models.CharField(max_length=150)
    event_description = models.TextField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.shipment.shipment_number} @ {self.location_name}"
