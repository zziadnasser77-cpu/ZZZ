from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import Currency
from apps.biomedical.models import ServiceTicket, WarrantyContract
from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.crm.models import Customer, Opportunity
from apps.inventory.models import Location, SerialAsset
from apps.payments.models import CustomerInvoice, InvoiceStatus


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gm_user(make_user):
    return make_user("gm@smses.local", roles=["GENERAL_MANAGER"], full_name="General Manager")


@pytest.fixture
def sales_rep_user(make_user):
    return make_user("rep@smses.local", roles=["SALES_REP"], full_name="Sales Rep")


@pytest.fixture
def sample_data(db):
    currency, _ = Currency.objects.get_or_create(
        code="USD",
        defaults={
            "name_ar": "دولار أمريكي",
            "name_en": "US Dollar",
            "symbol": "$",
            "decimals": 2,
            "is_active": True,
        },
    )

    customer = Customer.objects.create(
        customer_number="CUST-2026-000100",
        legal_name_ar="مستشفى الثورة العام",
        legal_name_en="Al-Thawra General Hospital",
        customer_type=Customer.CustomerType.HOSPITAL,
    )
    category = Category.objects.create(name_ar="أجهزة الأشعة", code="RAD")
    manufacturer = Manufacturer.objects.create(name_ar="الشركة الصينية للرعاية", code="CH-CARE")
    product = Product.objects.create(
        code="XRAY-500",
        name_ar="جهاز أشعة سينية رقمي",
        name_en="Digital X-Ray System",
        category=category,
        manufacturer=manufacturer,
    )
    model = ProductModel.objects.create(
        product=product,
        model_code="DR-500X",
        model_name="DR 500X Advanced",
        sku="SKU-DR500X",
        approval_status=ProductModel.ApprovalStatus.APPROVED,
    )
    location = Location.objects.create(
        code="WH-SANAA-MAIN",
        name_ar="المستودع الرئيسي - صنعاء",
        location_type=Location.LocationType.WAREHOUSE,
    )
    asset = SerialAsset.objects.create(
        serial_number="SN-RAD-2026-001",
        model=model,
        current_location=location,
        status=SerialAsset.Status.IN_STOCK,
    )

    currency = Currency.objects.get(code="USD")

    # Customer Invoice with balance
    invoice = CustomerInvoice.objects.create(
        customer=customer,
        invoice_date=timezone.now().date() - timedelta(days=45),
        due_date=timezone.now().date() - timedelta(days=15),
        currency=currency,
        subtotal=Decimal("25000.00"),
        total_amount=Decimal("25000.00"),
        paid_amount=Decimal("5000.00"),
        status=InvoiceStatus.POSTED,
    )

    # Opportunity
    Opportunity.objects.create(
        customer=customer,
        title="توريد جهاز أشعة للمستشفى",
        stage=Opportunity.Stage.PROPOSAL,
        expected_value=Decimal("50000.00"),
        probability_pct=60,
    )

    # Warranty
    WarrantyContract.objects.create(
        asset=asset,
        customer=customer,
        start_date=timezone.now().date() - timedelta(days=60),
        end_date=timezone.now().date() + timedelta(days=20),
        sla_response_hours=24,
        is_active=True,
    )

    # Service Ticket
    ServiceTicket.objects.create(
        asset=asset,
        customer=customer,
        title="فحص ومعايرة دورية",
        reported_issue="صيانة دورية مجدولة",
        ticket_type=ServiceTicket.TicketType.PREVENTIVE,
        priority=ServiceTicket.Priority.MEDIUM,
        status=ServiceTicket.Status.OPEN,
    )

    return {
        "customer": customer,
        "asset": asset,
        "invoice": invoice,
    }


@pytest.mark.django_db
def test_dashboard_summary_permission_isolation(api_client, gm_user, sales_rep_user, sample_data):
    # GM has financial access
    api_client.force_authenticate(user=gm_user)
    resp = api_client.get("/api/v1/reporting/dashboard/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["financial_access"] is True
    assert data["commercial"]["open_opportunities_count"] >= 1
    assert data["receivables"]["unpaid_invoices_count"] >= 1
    assert Decimal(data["receivables"]["unpaid_total"]) == Decimal("20000.00")
    assert data["biomedical"]["open_tickets_count"] >= 1

    # Sales rep does NOT have cost / financial viewing perms (§5.1)
    api_client.force_authenticate(user=sales_rep_user)
    resp_rep = api_client.get("/api/v1/reporting/dashboard/")
    assert resp_rep.status_code == 200
    rep_data = resp_rep.json()
    assert rep_data["financial_access"] is False


@pytest.mark.django_db
def test_commercial_pipeline_report(api_client, gm_user, sample_data):
    api_client.force_authenticate(user=gm_user)
    resp = api_client.get("/api/v1/reporting/commercial/")
    assert resp.status_code == 200
    data = resp.json()
    assert "opportunities_by_stage" in data
    assert "win_rate_percentage" in data
    assert "deals_by_commercial_model" in data


@pytest.mark.django_db
def test_receivables_aging_report(api_client, gm_user, sample_data):
    api_client.force_authenticate(user=gm_user)
    resp = api_client.get("/api/v1/reporting/receivables-aging/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["customers"]) >= 1
    cust_report = data["customers"][0]
    assert cust_report["customer_number"] == "CUST-2026-000100"
    assert Decimal(cust_report["total_outstanding"]) == Decimal("20000.00")
    # 15 days overdue falls in 1-30 days bucket
    assert Decimal(cust_report["days_1_30"]) == Decimal("20000.00")


@pytest.mark.django_db
def test_warranties_forecast_report(api_client, gm_user, sample_data):
    api_client.force_authenticate(user=gm_user)
    resp = api_client.get("/api/v1/reporting/warranties-forecast/")
    assert resp.status_code == 200
    data = resp.json()
    assert "expiring_30d" in data["warranties"]
    assert len(data["warranties"]["expiring_30d"]) >= 1


@pytest.mark.django_db
def test_maintenance_performance_report(api_client, gm_user, sample_data):
    api_client.force_authenticate(user=gm_user)
    resp = api_client.get("/api/v1/reporting/maintenance-performance/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tickets"] >= 1


@pytest.mark.django_db
def test_csv_exports(api_client, gm_user, sample_data):
    api_client.force_authenticate(user=gm_user)

    # 1. Receivables CSV
    r1 = api_client.get("/api/v1/reporting/export/receivables/")
    assert r1.status_code == 200
    assert "text/csv" in r1["Content-Type"]
    assert "CUST-2026-000100" in r1.content.decode("utf-8")

    # 2. Inventory assets CSV
    r2 = api_client.get("/api/v1/reporting/export/inventory-assets/")
    assert r2.status_code == 200
    assert "text/csv" in r2["Content-Type"]
    assert "SN-RAD-2026-001" in r2.content.decode("utf-8")

    # 3. Trial balance CSV
    r3 = api_client.get("/api/v1/reporting/export/trial-balance/")
    assert r3.status_code == 200
    assert "text/csv" in r3["Content-Type"]

    # 4. Audit log CSV
    r4 = api_client.get("/api/v1/reporting/export/audit-log/")
    assert r4.status_code == 200
    assert "text/csv" in r4["Content-Type"]
