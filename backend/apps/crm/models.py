from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.organization_settings.models import next_document_number


class Customer(BaseModel):
    """Customer profile (Hospitals, Centers, Clinics, Government, Distributors). Spec §5.2, §7."""

    class CustomerType(models.TextChoices):
        HOSPITAL = "HOSPITAL", "مستشفى"
        MEDICAL_CENTER = "MEDICAL_CENTER", "مركز طبي"
        CLINIC = "CLINIC", "عيادة خاصة"
        GOVERNMENT = "GOVERNMENT", "جهة حكومية / وزارة"
        DISTRIBUTOR = "DISTRIBUTOR", "موزع / تاجر فرعي"
        OTHER = "OTHER", "أخرى"

    class Status(models.TextChoices):
        LEAD = "LEAD", "محتمل"
        ACTIVE = "ACTIVE", "نشط"
        INACTIVE = "INACTIVE", "غير نشط"

    customer_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    customer_type = models.CharField(
        max_length=30, choices=CustomerType.choices, default=CustomerType.HOSPITAL
    )
    legal_name_ar = models.CharField(max_length=255, db_index=True)
    legal_name_en = models.CharField(max_length=255, blank=True)
    trade_name = models.CharField(max_length=255, blank=True)

    governorate = models.CharField(max_length=100, blank=True, help_text="المحافظة")
    district = models.CharField(max_length=100, blank=True, help_text="المديرية")
    address = models.TextField(blank=True)

    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=200, blank=True)

    commercial_register_no = models.CharField(max_length=60, blank=True)
    tax_no = models.CharField(max_length=60, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LEAD)
    assigned_sales_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_customers",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer_type", "status"]),
            models.Index(fields=["governorate"]),
        ]

    def __str__(self):
        return f"{self.customer_number} - {self.legal_name_ar}"

    def save(self, *args, **kwargs):
        if not self.customer_number:
            self.customer_number = next_document_number("customer", prefix="CUST")
        super().save(*args, **kwargs)


class Contact(BaseModel):
    """Customer personnel contact point (Purchasing, Biomed, Doctor, etc.). Spec §5.2."""

    class Role(models.TextChoices):
        MANAGEMENT = "MANAGEMENT", "إدارة عامة / مدير"
        PURCHASING = "PURCHASING", "مشتريات ومناقصات"
        BIOMEDICAL_ENGINEER = "BIOMEDICAL_ENGINEER", "مهندس طبي"
        DOCTOR = "DOCTOR", "طبيب / رئيس قسم"
        FINANCE = "FINANCE", "مالية / حسابات"
        OTHER = "OTHER", "أخرى"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=150)
    job_title = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.OTHER)

    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.name} ({self.customer.legal_name_ar})"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Unset other primary contacts for the same customer
            Contact.objects.filter(customer=self.customer, is_primary=True).exclude(pk=self.pk).update(
                is_primary=False
            )
        super().save(*args, **kwargs)


class Opportunity(BaseModel):
    """Sales Opportunity pipeline (stages, expected value, probability). Spec §5.2, §7."""

    class Stage(models.TextChoices):
        DISCOVERY = "DISCOVERY", "استكشاف وتحديد احتياج"
        QUALIFIED = "QUALIFIED", "مؤهل"
        PROPOSAL = "PROPOSAL", "تقديم عرض"
        NEGOTIATION = "NEGOTIATION", "تفاوض"
        WON = "WON", "فوز (مغلقة بنجاح)"
        LOST = "LOST", "خسارة"
        CANCELLED = "CANCELLED", "ملغاة"

    class Source(models.TextChoices):
        TENDER = "TENDER", "مناقصة حكومية / خاصة"
        DIRECT_CONTACT = "DIRECT_CONTACT", "زيارة / تواصل مباشر"
        REFERRAL = "REFERRAL", "توصية / عميل سابق"
        EXHIBITION = "EXHIBITION", "مؤتمر / معرض طبي"
        SUPPLIER_LEAD = "SUPPLIER_LEAD", "إحالة من المورد"
        OTHER = "OTHER", "أخرى"

    opportunity_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    title = models.CharField(max_length=255)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="opportunities")
    primary_contact = models.ForeignKey(
        Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="opportunities"
    )

    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.DISCOVERY, db_index=True)
    expected_value = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default="USD")
    probability_pct = models.PositiveSmallIntegerField(default=50, help_text="احتمال الإغلاق 0-100%")
    expected_close_date = models.DateField(null=True, blank=True)

    source = models.CharField(max_length=30, choices=Source.choices, default=Source.DIRECT_CONTACT)
    close_reason = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="opportunities",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "stage"]),
            models.Index(fields=["assigned_to", "stage"]),
        ]

    def __str__(self):
        return f"{self.opportunity_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.opportunity_number:
            self.opportunity_number = next_document_number("opportunity", prefix="OPP")
        super().save(*args, **kwargs)


class Activity(BaseModel):
    """Customer interaction: visits, calls, meetings, tasks, notes. Spec §5.2."""

    class ActivityType(models.TextChoices):
        VISIT = "VISIT", "زيارة ميدانية"
        CALL = "CALL", "اتصال هاتفي"
        MEETING = "MEETING", "اجتماع"
        DEMO = "DEMO", "عرض توضيحي / تجربة جهاز"
        TASK = "TASK", "مهمة متابعة"
        EMAIL = "EMAIL", "بريد إلكتروني"
        NOTE = "NOTE", "ملاحظة داخلية"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "مخطط"
        COMPLETED = "COMPLETED", "مكتمل"
        CANCELLED = "CANCELLED", "ملغي"

    activity_type = models.CharField(max_length=20, choices=ActivityType.choices, default=ActivityType.VISIT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.CASCADE, related_name="activities"
    )
    contact = models.ForeignKey(
        Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities"
    )
    opportunity = models.ForeignKey(
        Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities"
    )

    scheduled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="activities",
    )

    outcome = models.TextField(blank=True)
    next_action = models.CharField(max_length=255, blank=True)
    next_action_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-scheduled_at", "-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["performed_by", "status"]),
        ]

    def __str__(self):
        return f"{self.activity_type} - {self.subject}"
