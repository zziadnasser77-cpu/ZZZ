import string

from django.db import models, transaction
from django.utils import timezone

from apps.common.exceptions import BusinessRuleViolation
from apps.common.models import BaseModel

ALLOWED_SEQUENCE_FIELDS = {"prefix", "year", "seq", "branch"}


def validate_sequence_pattern(pattern: str) -> str:
    """Ensure pattern only references whitelisted placeholders with no attribute/index traversal."""
    if not pattern or len(pattern) > 80:
        raise BusinessRuleViolation("Invalid sequence pattern.")
    formatter = string.Formatter()
    seen_seq = False
    try:
        for _, field_name, format_spec, conversion in formatter.parse(pattern):
            if field_name is None:
                continue
            if conversion is not None or "." in field_name or "[" in field_name:
                raise BusinessRuleViolation("Attribute or index access is not allowed in pattern.")
            if field_name not in ALLOWED_SEQUENCE_FIELDS:
                raise BusinessRuleViolation(f"Unknown placeholder '{field_name}' in pattern.")
            if format_spec and not all(c in "0123456789d" for c in format_spec):
                raise BusinessRuleViolation("Invalid format specification in pattern.")
            if field_name == "seq":
                seen_seq = True
        if not seen_seq:
            raise BusinessRuleViolation("Pattern must include '{seq}'.")
        pattern.format(prefix="PRFX", year=2026, seq=1, branch="BR")
    except (ValueError, KeyError, IndexError) as exc:
        raise BusinessRuleViolation("Malformed sequence pattern.") from exc
    return pattern


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
        constraints = [
            models.CheckConstraint(condition=models.Q(singleton=True), name="org_profile_singleton")
        ]

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


def next_document_number(
    doc_type: str, *, prefix: str | None = None, branch: str = "", on_date=None, reset_yearly: bool = True
) -> str:
    """Atomically allocate the next number. Row-locked so concurrent calls never collide."""
    on_date = on_date or timezone.localdate()
    year = on_date.year if reset_yearly else 0
    with transaction.atomic():
        seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
            doc_type=doc_type,
            year=year,
            branch=branch,
            defaults={"prefix": prefix or doc_type.upper()[:6]},
        )
        validate_sequence_pattern(seq.pattern)
        number = seq.pattern.format(prefix=seq.prefix, year=on_date.year, seq=seq.next_value, branch=branch)
        seq.next_value += 1
        seq.save(update_fields=["next_value", "updated_at"])
    return number
