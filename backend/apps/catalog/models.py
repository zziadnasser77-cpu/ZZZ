from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Category(BaseModel):
    """Medical device classification (Radiology, Ultrasound, Patient Monitoring, etc.). Spec §5.3."""

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subcategories",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "categories"

    def __str__(self):
        return f"{self.code} - {self.name_ar}"


class Manufacturer(BaseModel):
    """Manufacturer / Principal (e.g. Chinese partner company). Spec §5.3."""

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    country = models.CharField(max_length=60, default="China")
    website = models.CharField(max_length=200, blank=True)
    is_primary_partner = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name_ar or self.name_en


class Product(BaseModel):
    """Product entity. Distinct from Model/Variant and Serial Asset (Spec §5.3, ADR-034)."""

    class DeviceClass(models.TextChoices):
        CLASS_I = "CLASS_I", "Class I (منخفض الخطورة)"
        CLASS_IIA = "CLASS_IIA", "Class IIa (متوسط الخطورة)"
        CLASS_IIB = "CLASS_IIB", "Class IIb (عالي الخطورة)"
        CLASS_III = "CLASS_III", "Class III (حرج / فائق الخطورة)"

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="products")
    device_class = models.CharField(max_length=20, choices=DeviceClass.choices, default=DeviceClass.CLASS_IIA)

    description_ar = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/%Y/%m/", null=True, blank=True, help_text="صورة المنتج الطبية")
    image_url = models.URLField(max_length=500, blank=True, help_text="رابط صورة المنتج")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["manufacturer", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name_ar}"


class ProductModel(BaseModel):
    """Specific technical model/variant with specifications and accessories (Spec §5.3)."""

    class ApprovalStatus(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        APPROVED = "APPROVED", "معتمد"
        DISCONTINUED = "DISCONTINUED", "متوقف إنتاجه"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="models")
    model_code = models.CharField(max_length=100, db_index=True)
    model_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True, db_index=True)

    specifications = models.JSONField(default=dict, blank=True, help_text="المواصفات الفنية التفصيلية")
    standard_warranty_months = models.PositiveSmallIntegerField(
        default=12, help_text="مدة الضمان القياسية بالأشهر"
    )
    standard_accessories = models.TextField(blank=True, help_text="الملحقات القياسية المرفقة")
    optional_accessories = models.TextField(blank=True, help_text="الملحقات والخيارات الإضافية")

    power_requirements = models.CharField(max_length=150, blank=True, help_text="مثل 220V 50Hz, 1200VA")
    origin_country = models.CharField(max_length=60, default="China")
    image = models.ImageField(upload_to="models/%Y/%m/", null=True, blank=True, help_text="صورة الموديل والجهاز الطبية")
    image_url = models.URLField(max_length=500, blank=True, help_text="رابط صورة الموديل والجهاز")

    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["model_code"]
        constraints = [
            models.UniqueConstraint(fields=["product", "model_code"], name="uniq_product_model_code")
        ]

    def __str__(self):
        return f"{self.product.name_ar} - {self.model_name} ({self.sku})"
