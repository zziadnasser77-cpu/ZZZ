from django.conf import settings
from django.db import models

from apps.catalog.models import ProductModel
from apps.common.models import BaseModel
from apps.organization_settings.models import next_document_number


class Location(BaseModel):
    """Physical or logical stock location. Spec §5.8, ADR-025."""

    class LocationType(models.TextChoices):
        WAREHOUSE = "WAREHOUSE", "مستودع رئيسي / فرعي"
        BRANCH = "BRANCH", "فرع الشركة"
        IN_TRANSIT = "IN_TRANSIT", "شحن وعبور (بحر / جو / بر)"
        CUSTOMER_SITE = "CUSTOMER_SITE", "موقع العميل (مستشفى / عيادة)"
        SUPPLIER_FACILITY = "SUPPLIER_FACILITY", "مصنع / مستودع المورد الصيني"
        MAINTENANCE_LAB = "MAINTENANCE_LAB", "مختبر وورشة الصيانة الطبية"
        CONSIGNMENT = "CONSIGNMENT", "أمانة / عهدة خارجية"

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    location_type = models.CharField(
        max_length=30,
        choices=LocationType.choices,
        default=LocationType.WAREHOUSE,
    )
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name_ar} ({self.location_type})"


class SerialAsset(BaseModel):
    """Specific serialized medical device instance. Spec §5.8, §7, ADR-023, ADR-024."""

    class Status(models.TextChoices):
        IN_STOCK = "IN_STOCK", "في المستودع"
        IN_TRANSIT = "IN_TRANSIT", "في الشحن والعبور"
        DELIVERED_TO_CUSTOMER = "DELIVERED_TO_CUSTOMER", "مسلّم للعميل"
        IN_MAINTENANCE = "IN_MAINTENANCE", "تحت الصيانة / الفحص"
        DEMO_LOAN = "DEMO_LOAN", "تجربة وعرض توضيحي للعميل (ديمو)"
        RESERVED = "RESERVED", "محجوز لصفقة"
        SCRAPPED = "SCRAPPED", "تالف / منسق"

    serial_number = models.CharField(max_length=100, unique=True, db_index=True)
    model = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="serial_assets")
    current_location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="assets")

    # Current snapshot of owner & custodian (maintained by OwnershipRecord and CustodyRecord)
    current_owner = models.CharField(max_length=150, default="SMSES Local Partner")
    current_custodian = models.CharField(max_length=150, default="Warehouse Custody")

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.IN_STOCK, db_index=True)
    manufacture_date = models.DateField(null=True, blank=True)
    cost_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=0.00, help_text="Specific identification cost"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["serial_number"]
        indexes = [
            models.Index(fields=["status", "current_location"]),
        ]

    def __str__(self):
        return f"{self.model.model_name} (S/N: {self.serial_number}) @ {self.current_location.code}"


class OwnershipRecord(BaseModel):
    """Separation of Legal Ownership from Physical Custody/Location. Spec §1.1, §5.8, ADR-023."""

    class OwnerType(models.TextChoices):
        LOCAL_COMPANY = "LOCAL_COMPANY", "الشركة المحلية (مخزون مملوك)"
        SUPPLIER = "SUPPLIER", "المورد / الشريك الصيني (بضاعة أمانة/وكالة)"
        CUSTOMER = "CUSTOMER", "العميل (جهاز مباع ومملوك له)"
        OTHER = "OTHER", "أخرى"

    asset = models.ForeignKey(SerialAsset, on_delete=models.CASCADE, related_name="ownership_history")
    owner_type = models.CharField(max_length=30, choices=OwnerType.choices, default=OwnerType.LOCAL_COMPANY)
    owner_name = models.CharField(max_length=150)
    effective_from = models.DateTimeField(db_index=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    proof_document_ref = models.CharField(
        max_length=120, blank=True, help_text="رقم فاتورة الشراء أو عقد البيع المثبت للملكية"
    )
    is_current = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.asset.serial_number} Owner: {self.owner_name} ({self.owner_type})"


class CustodyRecord(BaseModel):
    """Physical Custody tracker (Engineer loan, client demo, warehouse keeper). Spec §1.1, §5.8."""

    class CustodianType(models.TextChoices):
        USER = "USER", "موظف / مهندس / مندوب"
        CUSTOMER = "CUSTOMER", "عميل / مستشفى (تجربة أو أمانة)"
        SUPPLIER = "SUPPLIER", "مورد"
        CARRIER = "CARRIER", "ناقل / مخلص جمركي"

    asset = models.ForeignKey(SerialAsset, on_delete=models.CASCADE, related_name="custody_history")
    custodian_type = models.CharField(
        max_length=30, choices=CustodianType.choices, default=CustodianType.USER
    )
    custodian_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="asset_custodies",
    )
    custodian_name = models.CharField(max_length=150)
    effective_from = models.DateTimeField(db_index=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=150, help_text="e.g. Demonstration, Field Installation, Custody")
    is_current = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.asset.serial_number} Custodian: {self.custodian_name} ({self.purpose})"


class StockMovement(BaseModel):
    """Immutable ledger of all stock ins and outs. Balance is derived from movements. Spec §1.1, §5.8."""

    class MovementType(models.TextChoices):
        RECEIPT = "RECEIPT", "استلام توريد (مورد أو محلي)"
        ISSUE = "ISSUE", "صرف مخزني"
        TRANSFER = "TRANSFER", "نقل بين المواقع"
        SALE_DISPATCH = "SALE_DISPATCH", "صرف تسليم للعميل (أمر بيع)"
        RETURN = "RETURN", "إرجاع مخزني"
        ADJUSTMENT = "ADJUSTMENT", "تسوية جردية"

    movement_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    movement_type = models.CharField(max_length=30, choices=MovementType.choices)
    model = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="stock_movements")
    asset = models.ForeignKey(
        SerialAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements",
    )

    from_location = models.ForeignKey(
        Location,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="outward_movements",
    )
    to_location = models.ForeignKey(
        Location,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inward_movements",
    )

    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)

    reference_document = models.CharField(
        max_length=100, blank=True, help_text="e.g. PO-..., SO-..., STK-..."
    )
    is_posted = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model", "created_at"]),
            models.Index(fields=["from_location", "to_location"]),
        ]

    def __str__(self):
        return f"{self.movement_number} - {self.movement_type}: {self.quantity} x {self.model.model_code}"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.is_posted:
            raise PermissionError("Posted stock movements are append-only and cannot be modified.")
        if not self.movement_number:
            self.movement_number = next_document_number("stock_movement", prefix="SM")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Posted stock movements cannot be deleted; record a reversal movement instead.")


class StockCount(BaseModel):
    """Physical stock count / inventory audit. Spec §5.8, §6.5."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        IN_PROGRESS = "IN_PROGRESS", "جاري الجرد الفعلي"
        SUBMITTED = "SUBMITTED", "تم رفع الجرد للمراجعة"
        APPROVED = "APPROVED", "معتمد"
        POSTED = "POSTED", "مرحل وتم إنشاء قيود التسوية"
        CANCELLED = "CANCELLED", "ملغي"

    count_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="stock_counts")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    count_date = models.DateField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-count_date"]

    def __str__(self):
        return f"{self.count_number} @ {self.location.code} ({self.count_date})"

    def save(self, *args, **kwargs):
        if not self.count_number:
            self.count_number = next_document_number("stock_count", prefix="STK")
        super().save(*args, **kwargs)


class StockCountItem(BaseModel):
    """Discrepancy calculation between system calculated balance and physical count."""

    stock_count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="items")
    model = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="+")
    system_quantity = models.IntegerField(default=0)
    counted_quantity = models.IntegerField(default=0)
    discrepancy_quantity = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["model__model_code"]
        constraints = [models.UniqueConstraint(fields=["stock_count", "model"], name="uniq_count_model")]

    def __str__(self):
        return f"{self.model.model_code}: Sys {self.system_quantity} vs Count {self.counted_quantity} (Diff: {self.discrepancy_quantity})"

    def save(self, *args, **kwargs):
        self.discrepancy_quantity = self.counted_quantity - self.system_quantity
        super().save(*args, **kwargs)
