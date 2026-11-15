from decimal import Decimal

import pytest

from apps.accounting.models import Account, AccountType, Currency
from apps.common.exceptions import BusinessRuleViolation
from apps.crm.models import Customer
from apps.payments.models import (
    BankAccount,
    BankAccountType,
    CustomerInvoice,
    CustomerInvoiceLine,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    PaymentType,
    SupplierBill,
    SupplierBillLine,
    SupplierBillStatus,
)
from apps.payments.services import (
    allocate_payment,
    post_customer_invoice,
    post_payment,
    post_supplier_bill,
)
from apps.procurement.models import Supplier


@pytest.fixture
def payments_setup(db):
    yer, _ = Currency.objects.get_or_create(
        code="YER",
        defaults={"name_ar": "ريال يمني", "name_en": "Yemeni Rial", "symbol": "ر.ي", "is_base": True},
    )
    bank_gl, _ = Account.objects.get_or_create(
        code="1020",
        defaults={"name_ar": "البنك والنقدية", "name_en": "Bank", "account_type": AccountType.ASSET},
    )

    bank_account = BankAccount.objects.create(
        account_type=BankAccountType.BANK_ACCOUNT,
        name_ar="بنك التضامن الإسلامي",
        name_en="Tadhamon Bank",
        currency=yer,
        gl_account=bank_gl,
        opening_balance=Decimal("50000.00"),
        current_balance=Decimal("50000.00"),
    )

    customer = Customer.objects.create(
        legal_name_ar="مستشفى الأمل التخصصي",
        trade_name="الأمل",
        customer_type=Customer.CustomerType.HOSPITAL,
    )

    supplier = Supplier.objects.create(
        code="SUP-0001",
        name_ar="شنتشن للأجهزة الطبية",
        name_en="Shenzhen MedTech",
        country="CN",
    )

    return {
        "yer": yer,
        "bank_account": bank_account,
        "customer": customer,
        "supplier": supplier,
    }


@pytest.mark.django_db
def test_customer_invoice_creation_and_posting(payments_setup, admin_user):
    s = payments_setup
    invoice = CustomerInvoice.objects.create(
        customer=s["customer"],
        currency=s["yer"],
        created_by=admin_user,
    )
    CustomerInvoiceLine.objects.create(
        invoice=invoice,
        description="جهاز أشعة مقطعية",
        quantity=1,
        unit_price=Decimal("15000.00"),
    )

    posted_inv = post_customer_invoice(invoice, user=admin_user)

    assert posted_inv.status == InvoiceStatus.POSTED
    assert posted_inv.total_amount == Decimal("15000.00")
    assert posted_inv.remaining_amount == Decimal("15000.00")
    assert posted_inv.gl_entry is not None
    assert posted_inv.gl_entry.is_posted is True


@pytest.mark.django_db
def test_supplier_bill_creation_and_posting(payments_setup, admin_user):
    s = payments_setup
    bill = SupplierBill.objects.create(
        supplier=s["supplier"],
        currency=s["yer"],
        created_by=admin_user,
    )
    SupplierBillLine.objects.create(
        bill=bill,
        description="قطع غيار أجهزة طبية",
        quantity=5,
        unit_price=Decimal("2000.00"),
    )

    posted_bill = post_supplier_bill(bill, user=admin_user)

    assert posted_bill.status == SupplierBillStatus.POSTED
    assert posted_bill.total_amount == Decimal("10000.00")
    assert posted_bill.gl_entry is not None
    assert posted_bill.gl_entry.is_posted is True


@pytest.mark.django_db
def test_payment_posting_updates_bank_balance(payments_setup, admin_user):
    s = payments_setup
    initial_balance = s["bank_account"].current_balance

    payment = Payment.objects.create(
        payment_type=PaymentType.CUSTOMER_RECEIPT,
        customer=s["customer"],
        bank_account=s["bank_account"],
        amount=Decimal("12000.00"),
        currency=s["yer"],
        created_by=admin_user,
    )

    posted_pay = post_payment(payment, user=admin_user)

    assert posted_pay.status == PaymentStatus.POSTED
    s["bank_account"].refresh_from_db()
    assert s["bank_account"].current_balance == initial_balance + Decimal("12000.00")
    assert posted_pay.unallocated_amount == Decimal("12000.00")


@pytest.mark.django_db
def test_payment_allocation_across_invoices(payments_setup, admin_user):
    s = payments_setup
    # Create and post invoice 1: 600 YER
    inv1 = CustomerInvoice.objects.create(customer=s["customer"], currency=s["yer"], created_by=admin_user)
    CustomerInvoiceLine.objects.create(
        invoice=inv1, description="كشف 1", quantity=1, unit_price=Decimal("600.00")
    )
    post_customer_invoice(inv1, user=admin_user)

    # Create and post invoice 2: 800 YER
    inv2 = CustomerInvoice.objects.create(customer=s["customer"], currency=s["yer"], created_by=admin_user)
    CustomerInvoiceLine.objects.create(
        invoice=inv2, description="كشف 2", quantity=1, unit_price=Decimal("800.00")
    )
    post_customer_invoice(inv2, user=admin_user)

    # Customer pays 1000 YER
    payment = Payment.objects.create(
        payment_type=PaymentType.CUSTOMER_RECEIPT,
        customer=s["customer"],
        bank_account=s["bank_account"],
        amount=Decimal("1000.00"),
        currency=s["yer"],
        created_by=admin_user,
    )
    post_payment(payment, user=admin_user)

    # Allocate 600 to inv1
    allocate_payment(payment, invoice=inv1, amount=Decimal("600.00"), user=admin_user)
    inv1.refresh_from_db()
    assert inv1.status == InvoiceStatus.PAID
    assert inv1.paid_amount == Decimal("600.00")
    assert inv1.remaining_amount == Decimal("0.00")

    payment.refresh_from_db()
    assert payment.allocated_amount == Decimal("600.00")
    assert payment.unallocated_amount == Decimal("400.00")

    # Allocate remaining 400 to inv2
    allocate_payment(payment, invoice=inv2, amount=Decimal("400.00"), user=admin_user)
    inv2.refresh_from_db()
    assert inv2.status == InvoiceStatus.PARTIALLY_PAID
    assert inv2.paid_amount == Decimal("400.00")
    assert inv2.remaining_amount == Decimal("400.00")

    payment.refresh_from_db()
    assert payment.allocated_amount == Decimal("1000.00")
    assert payment.unallocated_amount == Decimal("0.00")


@pytest.mark.django_db
def test_over_allocation_blocked(payments_setup, admin_user):
    s = payments_setup
    inv = CustomerInvoice.objects.create(customer=s["customer"], currency=s["yer"], created_by=admin_user)
    CustomerInvoiceLine.objects.create(
        invoice=inv, description="بند", quantity=1, unit_price=Decimal("500.00")
    )
    post_customer_invoice(inv, user=admin_user)

    payment = Payment.objects.create(
        payment_type=PaymentType.CUSTOMER_RECEIPT,
        customer=s["customer"],
        bank_account=s["bank_account"],
        amount=Decimal("300.00"),
        currency=s["yer"],
        created_by=admin_user,
    )
    post_payment(payment, user=admin_user)

    # Attempt to allocate 400 when payment is only 300
    with pytest.raises(BusinessRuleViolation, match="يتجاوز المبلغ المتبقي غير الموزع"):
        allocate_payment(payment, invoice=inv, amount=Decimal("400.00"), user=admin_user)
