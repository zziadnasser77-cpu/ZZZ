from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.crm.models import Customer
from apps.inventory.models import Location, SerialAsset
from apps.organization_settings.models import next_document_number


class InstallationProtocol(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("مسودة - Draft")
        PENDING_REVIEW = "PENDING_REVIEW", _("قيد المراجعة - Pending Review")
        ACCEPTED = "ACCEPTED", _("معتمد ومسلّم - Accepted & Signed")
        REJECTED = "REJECTED", _("مرفوض - Rejected")

    protocol_number = models.CharField(max_length=32, unique=True, blank=True)
    asset = models.ForeignKey(SerialAsset, on_delete=models.PROTECT, related_name="installation_protocols")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="installation_protocols")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="installation_protocols")
    installed_at = models.DateField(default=timezone.now)
    lead_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="installations_led"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    electrical_safety_passed = models.BooleanField(default=False)
    performance_verification_passed = models.BooleanField(default=False)
    user_training_completed = models.BooleanField(default=False)
    trainees_list = models.TextField(blank=True, help_text="أسماء وتخصصات الكادر الطبي المتدرب")

    customer_representative_name = models.CharField(max_length=150, blank=True)
    customer_representative_title = models.CharField(max_length=100, blank=True)
    customer_signed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-installed_at", "-created_at"]
        verbose_name = _("محضر تركيب وتشغيل")
        verbose_name_plural = _("محاضر التركيب والتشغيل")

    def __str__(self):
        return f"{self.protocol_number} - {self.asset.serial_number} ({self.customer.legal_name_ar})"

    def save(self, *args, **kwargs):
        if not self.protocol_number:
            self.protocol_number = next_document_number("INSTALLATION_PROTOCOL", prefix="INST")
        super().save(*args, **kwargs)


class WarrantyContract(BaseModel):
    class WarrantyType(models.TextChoices):
        MANUFACTURER_WARRANTY = "MANUFACTURER_WARRANTY", _("ضمان الشركة المصنعة الصينية")
        CUSTOMER_WARRANTY = "CUSTOMER_WARRANTY", _("ضمان العميل المحلي")
        EXTENDED_MAINTENANCE = "EXTENDED_MAINTENANCE", _("عقد صيانة دورية ممتد")

    contract_number = models.CharField(max_length=32, unique=True, blank=True)
    asset = models.ForeignKey(SerialAsset, on_delete=models.PROTECT, related_name="warranty_contracts")
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.PROTECT, related_name="warranty_contracts"
    )
    warranty_type = models.CharField(
        max_length=30,
        choices=WarrantyType.choices,
        default=WarrantyType.CUSTOMER_WARRANTY,
    )
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField()
    sla_response_hours = models.PositiveIntegerField(default=24)
    coverage_details = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-end_date"]
        verbose_name = _("عقد وضمان طبي")
        verbose_name_plural = _("عقود وضمانات الأجهزة")

    def __str__(self):
        return f"{self.contract_number} ({self.get_warranty_type_display()}): {self.asset.serial_number}"

    def save(self, *args, **kwargs):
        if not self.contract_number:
            self.contract_number = next_document_number("WARRANTY_CONTRACT", prefix="WAR")
        super().save(*args, **kwargs)


class ServiceTicket(BaseModel):
    class TicketType(models.TextChoices):
        PREVENTIVE = "PREVENTIVE", _("صيانة وقائية دورية")
        CORRECTIVE = "CORRECTIVE", _("صيانة تصحيحية")
        EMERGENCY = "EMERGENCY", _("عطل طارئ وتوقف جهاز")
        CALIBRATION = "CALIBRATION", _("معايرة واختبار دقة")

    class Priority(models.TextChoices):
        LOW = "LOW", _("منخفضة")
        MEDIUM = "MEDIUM", _("متوسطة")
        HIGH = "HIGH", _("عالية")
        CRITICAL = "CRITICAL", _("حرجة جداً")

    class WarrantyStatus(models.TextChoices):
        UNDER_WARRANTY = "UNDER_WARRANTY", _("تحت الضمان")
        OUT_OF_WARRANTY = "OUT_OF_WARRANTY", _("خارج الضمان (مدفوع)")
        PENDING_ASSESSMENT = "PENDING_ASSESSMENT", _("قيد الفحص وتحديد الأهلية")

    class Status(models.TextChoices):
        OPEN = "OPEN", _("مفتوحة")
        ASSIGNED = "ASSIGNED", _("تم تعيين مهندس")
        IN_PROGRESS = "IN_PROGRESS", _("قيد التنفيذ")
        WAITING_PARTS = "WAITING_PARTS", _("في انتظار قطع الغيار")
        WAITING_CUSTOMER_APPROVAL = "WAITING_CUSTOMER_APPROVAL", _("في انتظار موافقة العميل على التكلفة")
        RESOLVED = "RESOLVED", _("تم الإصلاح")
        CLOSED = "CLOSED", _("مغلقة ومعتمدة")
        CANCELLED = "CANCELLED", _("ملغاة")

    ticket_number = models.CharField(max_length=32, unique=True, blank=True)
    ticket_type = models.CharField(max_length=20, choices=TicketType.choices, default=TicketType.CORRECTIVE)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    asset = models.ForeignKey(SerialAsset, on_delete=models.PROTECT, related_name="service_tickets")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="service_tickets")
    assigned_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )
    title = models.CharField(max_length=255)
    reported_issue = models.TextField()
    diagnostic_findings = models.TextField(blank=True)
    resolution_summary = models.TextField(blank=True)
    warranty_status = models.CharField(
        max_length=25,
        choices=WarrantyStatus.choices,
        default=WarrantyStatus.PENDING_ASSESSMENT,
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)

    labor_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    labor_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    parts_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    total_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))

    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tickets",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("تذكرة صيانة وخدمة")
        verbose_name_plural = _("تذاكر الصيانة والخدمة")

    def __str__(self):
        return f"{self.ticket_number} - {self.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = next_document_number("SERVICE_TICKET", prefix="SRV")
        self.total_cost = self.labor_cost + self.parts_cost
        super().save(*args, **kwargs)


class ServiceVisit(BaseModel):
    ticket = models.ForeignKey(ServiceTicket, on_delete=models.CASCADE, related_name="visits")
    engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="service_visits"
    )
    visit_date = models.DateField(default=timezone.now)
    actions_taken = models.TextField()
    diagnostic_details = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    customer_sign_off_name = models.CharField(max_length=150, blank=True)
    customer_signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-visit_date", "-created_at"]
        verbose_name = _("زيارة صيانة")
        verbose_name_plural = _("زيارات الصيانة")

    def __str__(self):
        return f"{self.ticket.ticket_number} - {self.visit_date} ({self.engineer.full_name or self.engineer.email})"


class SparePartRequest(BaseModel):
    class Coverage(models.TextChoices):
        WARRANTY_FREE = "WARRANTY_FREE", _("مغطى بالضمان مجاناً")
        BILLABLE_CUSTOMER = "BILLABLE_CUSTOMER", _("على حساب العميل")

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", _("تم الطلب")
        APPROVED_BY_PARTNER = "APPROVED_BY_PARTNER", _("معتمد من الشركة المصنعة")
        DISPATCHED_FROM_CHINA = "DISPATCHED_FROM_CHINA", _("تم الشحن من الصين")
        RECEIVED_LOCALLY = "RECEIVED_LOCALLY", _("تم الاستلام محلياً")
        INSTALLED = "INSTALLED", _("تم التركيب في الجهاز")
        REJECTED = "REJECTED", _("مرفوض")

    ticket = models.ForeignKey(ServiceTicket, on_delete=models.CASCADE, related_name="spare_parts")
    part_name = models.CharField(max_length=200)
    part_sku = models.CharField(max_length=100, blank=True, help_text="SKU المورد الصيني")
    quantity = models.PositiveIntegerField(default=1)
    coverage = models.CharField(max_length=25, choices=Coverage.choices, default=Coverage.WARRANTY_FREE)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REQUESTED)
    cost_price = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    customer_price = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_part_requests",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("طلب قطعة غيار")
        verbose_name_plural = _("طلبات قطع الغيار")

    def __str__(self):
        return f"{self.part_name} x{self.quantity} ({self.get_status_display()})"
