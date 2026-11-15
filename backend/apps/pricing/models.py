from django.db import models

from apps.catalog.models import ProductModel
from apps.common.models import BaseModel


class PriceList(BaseModel):
    """Price List with versioning and effective dates. Spec §5.3, ADR-029."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "مسودة"
        ACTIVE = "ACTIVE", "سارية"
        EXPIRED = "EXPIRED", "منتهية الصلاحية"
        ARCHIVED = "ARCHIVED", "مؤرشفة"

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    currency = models.CharField(max_length=3, default="USD")

    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from", "code"]

    def __str__(self):
        return f"{self.code} - {self.name_ar} ({self.currency})"

    def save(self, *args, **kwargs):
        if self.is_default:
            PriceList.objects.filter(is_default=True, currency=self.currency).exclude(pk=self.pk).update(
                is_default=False
            )
        super().save(*args, **kwargs)


class PriceListItem(BaseModel):
    """Price list entry per ProductModel with floor price and cost. Spec §5.3, ADR-029."""

    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="items")
    model = models.ForeignKey(ProductModel, on_delete=models.PROTECT, related_name="price_list_items")

    base_price = models.DecimalField(max_digits=18, decimal_places=2, help_text="سعر البيع المعتمد")
    min_price = models.DecimalField(
        max_digits=18, decimal_places=2, help_text="الحد الأدنى لسعر البيع المسموح به"
    )
    cost_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="تكلفة المورد (حقل حساس محمي بصلاحية خاصة)",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["model__model_code"]
        constraints = [models.UniqueConstraint(fields=["price_list", "model"], name="uniq_price_list_model")]

    def __str__(self):
        return f"{self.price_list.code} : {self.model.sku} = {self.base_price} {self.price_list.currency}"
