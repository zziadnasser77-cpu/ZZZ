from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounting.models import Account, AccountType, JournalEntry, JournalLine
from apps.accounting.services import post_journal_entry
from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation
from apps.payments.models import (
    BankAccount,
    CustomerInvoice,
    InvoiceStatus,
    Payment,
    PaymentAllocation,
    PaymentStatus,
    PaymentType,
    SupplierBill,
    SupplierBillStatus,
)


def _get_or_create_default_account(
    code: str, name_ar: str, name_en: str, account_type: AccountType
) -> Account:
    acc, _ = Account.objects.get_or_create(
        code=code,
        defaults={
            "name_ar": name_ar,
            "name_en": name_en,
            "account_type": account_type,
            "is_active": True,
        },
    )
    return acc


@transaction.atomic
def post_customer_invoice(invoice: CustomerInvoice, user=None) -> CustomerInvoice:
    if invoice.status in (InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID):
        raise BusinessRuleViolation(_("الفاتورة مرحلة بالفعل."))

    lines = list(invoice.lines.all())
    if not lines and invoice.total_amount == Decimal("0.00"):
        raise BusinessRuleViolation(_("لا يمكن ترحيل فاتورة فارغة."))

    if lines:
        invoice.subtotal = sum((line.subtotal for line in lines), Decimal("0.00"))
        invoice.total_amount = invoice.subtotal + invoice.tax_amount - invoice.discount_amount

    # Create Journal Entry: Dr Accounts Receivable (1120), Cr Sales Revenue (4100)
    ar_account = _get_or_create_default_account(
        "1120", "العملاء والذمم المدينة", "Accounts Receivable", AccountType.ASSET
    )
    rev_account = _get_or_create_default_account(
        "4100", "إيرادات المبيعات", "Sales Revenue", AccountType.REVENUE
    )

    je = JournalEntry.objects.create(
        entry_date=invoice.invoice_date,
        reference=invoice.invoice_number,
        description=f"فاتورة مبيعات رقم {invoice.invoice_number} - {invoice.customer.legal_name_ar}",
        source_document_type="CustomerInvoice",
        source_document_id=invoice.id,
        created_by=user,
    )

    base_total = round(invoice.total_amount * invoice.exchange_rate, 2)

    JournalLine.objects.create(
        entry=je,
        account=ar_account,
        description=f"استحقاق فاتورة {invoice.invoice_number}",
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        debit=invoice.total_amount,
        credit=Decimal("0.00"),
        base_debit=base_total,
        base_credit=Decimal("0.00"),
    )
    JournalLine.objects.create(
        entry=je,
        account=rev_account,
        description=f"إيراد فاتورة {invoice.invoice_number}",
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        debit=Decimal("0.00"),
        credit=invoice.total_amount,
        base_debit=Decimal("0.00"),
        base_credit=base_total,
    )

    post_journal_entry(je, user=user)

    invoice.status = InvoiceStatus.POSTED
    invoice.gl_entry = je
    invoice.save(update_fields=["subtotal", "total_amount", "status", "gl_entry", "updated_at"])

    log_event(
        "payments.customer_invoice_posted",
        actor=user,
        entity=invoice,
        summary=f"ترحيل فاتورة العميل {invoice.invoice_number}",
        changes={"total_amount": str(invoice.total_amount), "gl_entry": je.entry_number},
    )
    return invoice


@transaction.atomic
def post_supplier_bill(bill: SupplierBill, user=None) -> SupplierBill:
    if bill.status in (SupplierBillStatus.POSTED, SupplierBillStatus.PARTIALLY_PAID, SupplierBillStatus.PAID):
        raise BusinessRuleViolation(_("فاتورة المورد مرحلة بالفعل."))

    lines = list(bill.lines.all())
    if not lines and bill.total_amount == Decimal("0.00"):
        raise BusinessRuleViolation(_("لا يمكن ترحيل فاتورة مورد فارغة."))

    if lines:
        bill.total_amount = sum((line.subtotal for line in lines), Decimal("0.00"))

    # Create Journal Entry: Dr Purchases/Inventory (1130), Cr Accounts Payable (2110)
    inv_account = _get_or_create_default_account(
        "1130", "مخزون الأجهزة الطبية", "Medical Equipment Inventory", AccountType.ASSET
    )
    ap_account = _get_or_create_default_account(
        "2110", "الموردون والذمم الدائنة", "Accounts Payable", AccountType.LIABILITY
    )

    je = JournalEntry.objects.create(
        entry_date=bill.bill_date,
        reference=bill.bill_number,
        description=f"فاتورة مورد رقم {bill.bill_number} - {bill.supplier.name_ar}",
        source_document_type="SupplierBill",
        source_document_id=bill.id,
        created_by=user,
    )

    base_total = round(bill.total_amount * bill.exchange_rate, 2)

    JournalLine.objects.create(
        entry=je,
        account=inv_account,
        description=f"مشتريات فاتورة مورد {bill.bill_number}",
        currency=bill.currency,
        exchange_rate=bill.exchange_rate,
        debit=bill.total_amount,
        credit=Decimal("0.00"),
        base_debit=base_total,
        base_credit=Decimal("0.00"),
    )
    JournalLine.objects.create(
        entry=je,
        account=ap_account,
        description=f"التزام فاتورة مورد {bill.bill_number}",
        currency=bill.currency,
        exchange_rate=bill.exchange_rate,
        debit=Decimal("0.00"),
        credit=bill.total_amount,
        base_debit=Decimal("0.00"),
        base_credit=base_total,
    )

    post_journal_entry(je, user=user)

    bill.status = SupplierBillStatus.POSTED
    bill.gl_entry = je
    bill.save(update_fields=["total_amount", "status", "gl_entry", "updated_at"])

    log_event(
        "payments.supplier_bill_posted",
        actor=user,
        entity=bill,
        summary=f"ترحيل فاتورة المورد {bill.bill_number}",
        changes={"total_amount": str(bill.total_amount), "gl_entry": je.entry_number},
    )
    return bill


@transaction.atomic
def post_payment(payment: Payment, user=None) -> Payment:
    if payment.status == PaymentStatus.POSTED:
        raise BusinessRuleViolation(_("السند مرحل بالفعل."))

    bank = BankAccount.objects.select_for_update().get(pk=payment.bank_account_id)

    if payment.payment_type == PaymentType.CUSTOMER_RECEIPT:
        bank.current_balance += payment.amount
    elif payment.payment_type == PaymentType.SUPPLIER_DISBURSEMENT:
        bank.current_balance -= payment.amount
    bank.save(update_fields=["current_balance", "updated_at"])

    # Create Journal Entry
    # Bank GL Account
    bank_gl = bank.gl_account or _get_or_create_default_account(
        "1020", "البنك والنقدية", "Cash & Bank", AccountType.ASSET
    )
    base_total = round(payment.amount * payment.exchange_rate, 2)

    je = JournalEntry.objects.create(
        entry_date=payment.payment_date,
        reference=payment.payment_number,
        description=f"{payment.get_payment_type_display()} {payment.payment_number}",
        source_document_type="Payment",
        source_document_id=payment.id,
        created_by=user,
    )

    if payment.payment_type == PaymentType.CUSTOMER_RECEIPT:
        ar_account = _get_or_create_default_account(
            "1120", "العملاء والذمم المدينة", "Accounts Receivable", AccountType.ASSET
        )
        # Dr Bank, Cr AR
        JournalLine.objects.create(
            entry=je,
            account=bank_gl,
            description=f"قبض دفعة {payment.payment_number}",
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            debit=payment.amount,
            credit=Decimal("0.00"),
            base_debit=base_total,
            base_credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            entry=je,
            account=ar_account,
            description=f"سداد عميل {payment.payment_number}",
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            debit=Decimal("0.00"),
            credit=payment.amount,
            base_debit=Decimal("0.00"),
            base_credit=base_total,
        )
    else:
        ap_account = _get_or_create_default_account(
            "2110", "الموردون والذمم الدائنة", "Accounts Payable", AccountType.LIABILITY
        )
        # Dr AP, Cr Bank
        JournalLine.objects.create(
            entry=je,
            account=ap_account,
            description=f"صرف للمورد {payment.payment_number}",
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            debit=payment.amount,
            credit=Decimal("0.00"),
            base_debit=base_total,
            base_credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            entry=je,
            account=bank_gl,
            description=f"صرف من حساب {payment.payment_number}",
            currency=payment.currency,
            exchange_rate=payment.exchange_rate,
            debit=Decimal("0.00"),
            credit=payment.amount,
            base_debit=Decimal("0.00"),
            base_credit=base_total,
        )

    post_journal_entry(je, user=user)

    payment.status = PaymentStatus.POSTED
    payment.gl_entry = je
    payment.save(update_fields=["status", "gl_entry", "updated_at"])

    log_event(
        "payments.payment_posted",
        actor=user,
        entity=payment,
        summary=f"ترحيل السند {payment.payment_number}",
        changes={"amount": str(payment.amount), "gl_entry": je.entry_number},
    )
    return payment


@transaction.atomic
def allocate_payment(
    payment: Payment,
    invoice: CustomerInvoice | None = None,
    bill: SupplierBill | None = None,
    amount: Decimal | None = None,
    user=None,
) -> PaymentAllocation:
    """Allocates part or all of a payment to a customer invoice or supplier bill."""
    if payment.status != PaymentStatus.POSTED:
        raise BusinessRuleViolation(_("يجب ترحيل السند قبل توزيع مبالغه على الفواتير."))

    if amount is None or amount <= Decimal("0.00"):
        raise BusinessRuleViolation(_("يجب تحديد مبلغ توزيع أكبر من الصفر."))

    if amount > payment.unallocated_amount:
        raise BusinessRuleViolation(
            _(
                f"المبلغ المطلوب توزيعه ({amount}) يتجاوز المبلغ المتبقي غير الموزع ({payment.unallocated_amount})."
            )
        )

    if not invoice and not bill:
        raise BusinessRuleViolation(_("يجب تحديد فاتورة عميل أو فاتورة مورد للتوزيع."))

    allocation = PaymentAllocation.objects.create(
        payment=payment,
        invoice=invoice,
        bill=bill,
        allocated_amount=amount,
        allocated_at=timezone.now(),
    )

    if invoice:
        if invoice.status not in (InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID):
            raise BusinessRuleViolation(_("لا يمكن توزيع دفعة إلا على فاتورة عميل مرحلة."))
        if amount > invoice.remaining_amount:
            raise BusinessRuleViolation(
                _(f"مبلغ التوزيع ({amount}) يتجاوز المتبقي من الفاتورة ({invoice.remaining_amount}).")
            )
        invoice.paid_amount += amount
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        invoice.save(update_fields=["paid_amount", "status", "updated_at"])

    if bill:
        if bill.status not in (SupplierBillStatus.POSTED, SupplierBillStatus.PARTIALLY_PAID):
            raise BusinessRuleViolation(_("لا يمكن توزيع دفعة إلا على فاتورة مورد مرحلة."))
        if amount > bill.remaining_amount:
            raise BusinessRuleViolation(
                _(f"مبلغ التوزيع ({amount}) يتجاوز المتبقي من فاتورة المورد ({bill.remaining_amount}).")
            )
        bill.paid_amount += amount
        if bill.paid_amount >= bill.total_amount:
            bill.status = SupplierBillStatus.PAID
        else:
            bill.status = SupplierBillStatus.PARTIALLY_PAID
        bill.save(update_fields=["paid_amount", "status", "updated_at"])

    payment.allocated_amount += amount
    payment.unallocated_amount -= amount
    payment.save(update_fields=["allocated_amount", "unallocated_amount", "updated_at"])

    log_event(
        "payments.payment_allocated",
        actor=user,
        entity=allocation,
        summary=f"توزيع مبلغ {amount} من السند {payment.payment_number}",
        changes={
            "payment": payment.payment_number,
            "invoice": invoice.invoice_number if invoice else None,
            "bill": bill.bill_number if bill else None,
            "amount": str(amount),
        },
    )
    return allocation
