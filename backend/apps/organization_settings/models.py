from django.db import models, transaction
from django.utils import timezone

from apps.common.models import BaseModel


class OrganizationProfile(BaseModel):
    """Single-company settings (ADR-001). Exactly one row (pk enforced by constraint)."""

    singleton = models.BooleanField(default=True, unique=True, editable=False)
    legal_name_ar = models.CharField(max_length=200, blank=True)
    legal_name_en = models.CharField(max_length=200, blank=True)
    trade_name = models.CharField(max_length=200, blank=True)
    commercial_register_no = models.CharField(max_length=60, blank=True)
    tax_no = models.CharField(max_length=60, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    logo_url = models.CharField(max_length=300, blank=True)
    base_currency = models.CharField(max_length=3, default="YER")
    default_language = models.CharField(max_length=5, default="ar")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(singleton=True), name="org_profile_singleton")]

    @classmethod
    def load(cls) -> "OrganizationProfile":
        obj, _ = cls.objects.get_or_create(singleton=True)
        return obj


class DocumentSequence(BaseModel):
    """Human-readable gap-free(ish) document numbers per type/year/branch (spec §18.1)."""

    doc_type = models.CharField(max_length=40)
    year = models.PositiveSmallIntegerField(default=0, help_text="0 = never resets")
    branch = models.CharField(max_length=20, blank=True)
    prefix = models.CharField(max_length=20)
    pattern = models.CharField(max_length=80, default="{prefix}-{year}-{seq:06d}")
    next_value = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["doc_type", "year", "branch"], name="uniq_doc_sequence")
        ]


def next_document_number(doc_type: str, *, prefix: str | None = None, branch: str = "",
                         on_date=None, reset_yearly: bool = True) -> str:
    """Atomically allocate the next number. Row-locked so concurrent calls never collide."""
    on_date = on_date or timezone.localdate()
    year = on_date.year if reset_yearly else 0
    with transaction.atomic():
        seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
            doc_type=doc_type, year=year, branch=branch,
            defaults={"prefix": prefix or doc_type.upper()[:6]},
        )
        number = seq.pattern.format(prefix=seq.prefix, year=on_date.year, seq=seq.next_value, branch=branch)
        seq.next_value += 1
        seq.save(update_fields=["next_value", "updated_at"])
    return number
