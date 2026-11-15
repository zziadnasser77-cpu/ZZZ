from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounting.models import (
    AccountType,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)
from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation


@transaction.atomic
def post_journal_entry(entry: JournalEntry, user=None) -> JournalEntry:
    """Verifies that a journal entry is balanced and posts it."""
    if entry.is_posted:
        raise BusinessRuleViolation(_("القيد مرحل بالفعل ولا يمكن ترحيله مرة أخرى."))

    lines = list(entry.lines.select_for_update())
    if not lines:
        raise BusinessRuleViolation(_("لا يمكن ترحيل قيد بدون أسطر."))

    total_debit = sum((line.base_debit for line in lines), Decimal("0.00"))
    total_credit = sum((line.base_credit for line in lines), Decimal("0.00"))

    if total_debit == Decimal("0.00"):
        raise BusinessRuleViolation(_("لا يمكن ترحيل قيد بقيمة صفرية."))

    if total_debit != total_credit:
        raise BusinessRuleViolation(
            _(f"القيد غير متوازن: مجموع المدين ({total_debit}) لا يساوي مجموع الدائن ({total_credit}).")
        )

    entry.status = JournalEntryStatus.POSTED
    entry.posted_by = user
    entry.posted_at = timezone.now()
    entry.save(update_fields=["status", "posted_by", "posted_at", "updated_at"])

    log_event(
        "accounting.journal_entry_posted",
        actor=user,
        entity=entry,
        summary=f"ترحيل القيد المحاسبي {entry.entry_number}",
        changes={"total_debit": str(total_debit), "total_credit": str(total_credit)},
    )
    return entry


@transaction.atomic
def reverse_journal_entry(entry: JournalEntry, user=None, reason: str = "") -> JournalEntry:
    """Creates and posts an opposite reversing entry for a posted entry."""
    if entry.status != JournalEntryStatus.POSTED:
        raise BusinessRuleViolation(_("لا يمكن عكس إلا القيود المرحلة فقط."))

    if entry.reversed_entry_id:
        raise BusinessRuleViolation(_("هذا القيد تم عكسه مسبقاً."))

    rev_desc = f"عكس القيد {entry.entry_number}"
    if reason:
        rev_desc = f"{rev_desc}: {reason}"

    rev_entry = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        reference=f"REV-{entry.entry_number}",
        description=rev_desc,
        source_document_type="JournalEntry",
        source_document_id=entry.id,
        created_by=user,
    )

    for line in entry.lines.all():
        JournalLine.objects.create(
            entry=rev_entry,
            account=line.account,
            description=f"عكس: {line.description}" if line.description else "",
            currency=line.currency,
            exchange_rate=line.exchange_rate,
            debit=line.credit,
            credit=line.debit,
            base_debit=line.base_credit,
            base_credit=line.base_debit,
        )

    post_journal_entry(rev_entry, user=user)

    entry.status = JournalEntryStatus.REVERSED
    entry.reversed_entry = rev_entry
    entry.save(update_fields=["status", "reversed_entry", "updated_at"])

    log_event(
        "accounting.journal_entry_reversed",
        actor=user,
        entity=entry,
        summary=f"عكس القيد المحاسبي {entry.entry_number} بالقيد {rev_entry.entry_number}",
        changes={"reversal_entry_number": rev_entry.entry_number, "reason": reason},
    )
    return rev_entry


def get_trial_balance(as_of_date: str | None = None) -> dict:
    """Computes trial balance across all accounts for posted entries."""
    qs = JournalLine.objects.filter(entry__status=JournalEntryStatus.POSTED)
    if as_of_date:
        qs = qs.filter(entry__entry_date__lte=as_of_date)

    aggregated = (
        qs.values(
            "account_id", "account__code", "account__name_ar", "account__name_en", "account__account_type"
        )
        .annotate(
            total_debit=Sum("base_debit"),
            total_credit=Sum("base_credit"),
        )
        .order_by("account__code")
    )

    accounts_data = []
    grand_debit = Decimal("0.00")
    grand_credit = Decimal("0.00")

    for row in aggregated:
        dr = row["total_debit"] or Decimal("0.00")
        cr = row["total_credit"] or Decimal("0.00")
        acc_type = row["account__account_type"]
        if acc_type in (AccountType.ASSET, AccountType.EXPENSE):
            balance = dr - cr
        else:
            balance = cr - dr

        grand_debit += dr
        grand_credit += cr

        accounts_data.append(
            {
                "account_id": str(row["account_id"]),
                "code": row["account__code"],
                "name_ar": row["account__name_ar"],
                "name_en": row["account__name_en"],
                "account_type": acc_type,
                "debit": float(dr),
                "credit": float(cr),
                "balance": float(balance),
            }
        )

    return {
        "accounts": accounts_data,
        "total_debit": float(grand_debit),
        "total_credit": float(grand_credit),
        "is_balanced": grand_debit == grand_credit,
    }
