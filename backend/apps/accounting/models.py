from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleViolation
from apps.common.models import BaseModel
from apps.organization_settings.models import next_document_number


class Currency(BaseModel):
    code = models.CharField(max_length=3, unique=True)  # YER, USD, CNY, SAR, AED, EUR
    name_ar = models.CharField(max_length=50)
    name_en = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10)
    is_base = models.BooleanField(default=False)
    decimals = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = _("عملة")
        verbose_name_plural = _("العملات")

    def __str__(self):
        return f"{self.code} - {self.name_ar}"

    def save(self, *args, **kwargs):
        if self.is_base:
            Currency.objects.exclude(pk=self.pk).filter(is_base=True).update(is_base=False)
        super().save(*args, **kwargs)


class ExchangeRate(BaseModel):
    class Source(models.TextChoices):
        CENTRAL_BANK = "CENTRAL_BANK", _("البنك المركزي")
        MARKET = "MARKET", _("السوق الموازي")
        CUSTOM = "CUSTOM", _("سعر مخصص")

    from_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="rates_from")
    to_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="rates_to")
    rate = models.DecimalField(max_digits=16, decimal_places=6)
    effective_date = models.DateField(default=timezone.now)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CENTRAL_BANK)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-effective_date", "-created_at"]
        verbose_name = _("سعر صرف")
        verbose_name_plural = _("أسعار الصرف")

    def __str__(self):
        return f"1 {self.from_currency.code} = {self.rate} {self.to_currency.code} ({self.effective_date})"


class AccountType(models.TextChoices):
    ASSET = "ASSET", _("أصول - Asset")
    LIABILITY = "LIABILITY", _("خصوم - Liability")
    EQUITY = "EQUITY", _("حقوق ملكية - Equity")
    REVENUE = "REVENUE", _("إيرادات - Revenue")
    EXPENSE = "EXPENSE", _("مصروفات - Expense")


class Account(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.RESTRICT, related_name="children"
    )
    currency = models.ForeignKey(
        Currency, null=True, blank=True, on_delete=models.PROTECT, related_name="accounts"
    )
    is_reconcilable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = _("حساب مالي")
        verbose_name_plural = _("دليل الحسابات")

    def __str__(self):
        return f"{self.code} - {self.name_ar}"


class JournalEntryStatus(models.TextChoices):
    DRAFT = "DRAFT", _("مسودة - Draft")
    PENDING_REVIEW = "PENDING_REVIEW", _("قيد المراجعة - Pending Review")
    APPROVED = "APPROVED", _("معتمد - Approved")
    POSTED = "POSTED", _("مرحل - Posted")
    REVERSED = "REVERSED", _("معكوس - Reversed")


class JournalEntry(BaseModel):
    entry_number = models.CharField(max_length=32, unique=True, blank=True)
    entry_date = models.DateField(default=timezone.now)
    reference = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=JournalEntryStatus.choices,
        default=JournalEntryStatus.DRAFT,
    )
    source_document_type = models.CharField(max_length=50, blank=True)
    source_document_id = models.UUIDField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries_created",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries_posted",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    reversed_entry = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversal_of",
    )

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        verbose_name = _("قيد يومية")
        verbose_name_plural = _("قيود اليومية")

    def __str__(self):
        return f"{self.entry_number} ({self.status}) - {self.description}"

    @property
    def is_posted(self) -> bool:
        return self.status in (JournalEntryStatus.POSTED, JournalEntryStatus.REVERSED)

    def delete(self, *args, **kwargs):
        if self.is_posted:
            raise BusinessRuleViolation(_("لا يمكن حذف القيود المرحلة أو المعكوسة. يجب عمل قيد عكسي."))
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.pk:
            orig = JournalEntry.objects.filter(pk=self.pk).values("status").first()
            if orig and orig["status"] == JournalEntryStatus.POSTED:
                update_fields = kwargs.get("update_fields")
                allowed_fields = {"status", "updated_at", "reversed_entry", "reversed_entry_id"}
                if update_fields and not set(update_fields).issubset(allowed_fields):
                    raise BusinessRuleViolation(_("القيود المرحلة غير قابلة للتعديل."))
                elif not update_fields and self.status != JournalEntryStatus.REVERSED:
                    raise BusinessRuleViolation(_("القيود المرحلة غير قابلة للتعديل."))
        if not self.entry_number:
            self.entry_number = next_document_number("JOURNAL_ENTRY", prefix="JE")
        super().save(*args, **kwargs)


class JournalLine(BaseModel):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    description = models.CharField(max_length=255, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="journal_lines")
    exchange_rate = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal("1.000000"))
    debit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    base_debit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    base_credit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("سطر قيد")
        verbose_name_plural = _("أسطر القيد")

    def __str__(self):
        return f"{self.account.code}: Dr {self.base_debit} / Cr {self.base_credit}"

    def save(self, *args, **kwargs):
        if self.entry.is_posted:
            raise BusinessRuleViolation(_("لا يمكن تعديل أو إضافة أسطر لقيد مرحل أو معكوس."))
        if self.debit > 0 and self.credit > 0:
            raise BusinessRuleViolation(_("لا يمكن أن يحتوي السطر على مدين ودائن معاً."))
        if self.debit < 0 or self.credit < 0:
            raise BusinessRuleViolation(_("لا يمكن أن تكون قيمة المدين أو الدائن سالبة."))
        if self.base_debit == 0 and self.debit > 0:
            self.base_debit = round(self.debit * self.exchange_rate, 2)
        if self.base_credit == 0 and self.credit > 0:
            self.base_credit = round(self.credit * self.exchange_rate, 2)
        super().save(*args, **kwargs)
