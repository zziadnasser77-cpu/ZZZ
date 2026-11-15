from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounting.models import (
    Account,
    AccountType,
    Currency,
    ExchangeRate,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)
from apps.accounting.services import (
    get_trial_balance,
    post_journal_entry,
    reverse_journal_entry,
)
from apps.common.exceptions import BusinessRuleViolation


@pytest.fixture
def accounting_setup(db):
    yer, _ = Currency.objects.get_or_create(
        code="YER",
        defaults={"name_ar": "ريال يمني", "name_en": "Yemeni Rial", "symbol": "ر.ي", "is_base": True},
    )
    usd, _ = Currency.objects.get_or_create(
        code="USD", defaults={"name_ar": "دولار", "name_en": "Dollar", "symbol": "$", "is_base": False}
    )
    ExchangeRate.objects.get_or_create(
        from_currency=usd,
        to_currency=yer,
        effective_date=timezone.now().date(),
        defaults={"rate": Decimal("535.000000")},
    )

    cash, _ = Account.objects.get_or_create(
        code="1010", defaults={"name_ar": "صندوق", "name_en": "Cash", "account_type": AccountType.ASSET}
    )
    ar, _ = Account.objects.get_or_create(
        code="1120", defaults={"name_ar": "عملاء", "name_en": "AR", "account_type": AccountType.ASSET}
    )
    sales, _ = Account.objects.get_or_create(
        code="4100", defaults={"name_ar": "مبيعات", "name_en": "Sales", "account_type": AccountType.REVENUE}
    )

    return {"yer": yer, "usd": usd, "cash": cash, "ar": ar, "sales": sales}


@pytest.mark.django_db
def test_balanced_journal_entry_posting(accounting_setup, admin_user):
    s = accounting_setup
    entry = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        description="بيع نقدي تجريبي",
        created_by=admin_user,
    )
    # Dr Cash 1000, Cr Sales 1000
    JournalLine.objects.create(
        entry=entry,
        account=s["cash"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("1000.00"),
        credit=Decimal("0.00"),
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["sales"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("0.00"),
        credit=Decimal("1000.00"),
    )

    posted = post_journal_entry(entry, user=admin_user)
    assert posted.status == JournalEntryStatus.POSTED
    assert posted.posted_by == admin_user
    assert posted.posted_at is not None
    assert posted.is_posted is True


@pytest.mark.django_db
def test_unbalanced_journal_entry_rejected(accounting_setup, admin_user):
    s = accounting_setup
    entry = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        description="قيد غير متوازن",
        created_by=admin_user,
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["cash"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("1000.00"),
        credit=Decimal("0.00"),
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["sales"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("0.00"),
        credit=Decimal("800.00"),
    )

    with pytest.raises(BusinessRuleViolation, match="غير متوازن"):
        post_journal_entry(entry, user=admin_user)


@pytest.mark.django_db
def test_posted_journal_entry_is_immutable(accounting_setup, admin_user):
    s = accounting_setup
    entry = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        description="قيد محمي من التعديل",
        created_by=admin_user,
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["cash"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("500.00"),
        credit=Decimal("0.00"),
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["sales"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("0.00"),
        credit=Decimal("500.00"),
    )
    post_journal_entry(entry, user=admin_user)

    # Deletion blocked
    with pytest.raises(BusinessRuleViolation, match="لا يمكن حذف القيود المرحلة"):
        entry.delete()

    # Updating description blocked
    entry.description = "تعديل غير مسموح"
    with pytest.raises(BusinessRuleViolation, match="غير قابلة للتعديل"):
        entry.save()


@pytest.mark.django_db
def test_reversal_creates_opposite_entry_and_links(accounting_setup, admin_user):
    s = accounting_setup
    entry = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        description="قيد أصل للعكس",
        created_by=admin_user,
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["cash"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("2500.00"),
        credit=Decimal("0.00"),
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["sales"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("0.00"),
        credit=Decimal("2500.00"),
    )
    post_journal_entry(entry, user=admin_user)

    rev_entry = reverse_journal_entry(entry, user=admin_user, reason="خطأ في الحساب")

    assert rev_entry.status == JournalEntryStatus.POSTED
    assert rev_entry.reference == f"REV-{entry.entry_number}"

    lines = list(rev_entry.lines.all())
    assert len(lines) == 2
    cash_line = next(line for line in lines if line.account_id == s["cash"].id)
    sales_line = next(line for line in lines if line.account_id == s["sales"].id)

    # Cash was debited, in reversal it must be credited
    assert cash_line.credit == Decimal("2500.00")
    assert cash_line.debit == Decimal("0.00")
    # Sales was credited, in reversal it must be debited
    assert sales_line.debit == Decimal("2500.00")
    assert sales_line.credit == Decimal("0.00")

    entry.refresh_from_db()
    assert entry.status == JournalEntryStatus.REVERSED
    assert entry.reversed_entry_id == rev_entry.id


@pytest.mark.django_db
def test_trial_balance_calculation(accounting_setup, admin_user):
    s = accounting_setup
    entry = JournalEntry.objects.create(
        entry_date=timezone.now().date(),
        description="مبيعات للعميل",
        created_by=admin_user,
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["ar"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("7000.00"),
        credit=Decimal("0.00"),
    )
    JournalLine.objects.create(
        entry=entry,
        account=s["sales"],
        currency=s["yer"],
        exchange_rate=Decimal("1.000000"),
        debit=Decimal("0.00"),
        credit=Decimal("7000.00"),
    )
    post_journal_entry(entry, user=admin_user)

    tb = get_trial_balance()
    assert tb["is_balanced"] is True
    assert tb["total_debit"] >= 7000.0
    assert tb["total_credit"] >= 7000.0
