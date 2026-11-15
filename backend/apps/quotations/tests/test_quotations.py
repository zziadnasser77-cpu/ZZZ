from decimal import Decimal

import pytest

from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.crm.models import Customer
from apps.quotations.models import Quotation, QuotationLine, QuotationVersion

pytestmark = pytest.mark.django_db


@pytest.fixture
def quote_setup():
    cust = Customer.objects.create(legal_name_ar="مستشفى الحياة التخصصي", governorate="تعز")
    cat = Category.objects.create(code="XR", name_ar="الأشعة السينية", name_en="X-Ray")
    mfg = Manufacturer.objects.create(code="CH-OEM", name_ar="المصنع الصيني", name_en="China OEM")
    prod = Product.objects.create(
        code="XR-DIGI", name_ar="جهاز أشعة رقمي", name_en="Digital X-Ray", category=cat, manufacturer=mfg
    )
    model = ProductModel.objects.create(
        product=prod, model_code="XR-500", model_name="XR 500 Digital", sku="SKU-XR-500"
    )
    return {"customer": cust, "model": model}


def test_quotation_creation_and_auto_v1(quote_setup, make_user, auth_client):
    sales_rep = make_user("rep@x.com", roles=["SALES_REP"])
    client = auth_client(sales_rep)

    data = {
        "title": "عرض توريد جهاز أشعة رقمية",
        "customer": str(quote_setup["customer"].id),
        "commercial_model": "DIRECT_SALE",
        "currency": "USD",
    }
    r = client.post("/api/v1/quotations/", data, format="json")
    assert r.status_code == 201, r.data
    assert r.data["quotation_number"].startswith("QT-")
    assert r.data["current_version_number"] == 1
    assert r.data["latest_version"]["version_number"] == 1


def test_discount_ceiling_triggers_approval_and_blocks_self_approval(quote_setup, make_user, auth_client):
    # Sales rep has a 5.00% max discount limit
    sales_rep = make_user("rep@x.com", roles=["SALES_REP"], discount_limit_pct=Decimal("5.00"))
    sales_mgr = make_user("mgr@x.com", roles=["SALES_MANAGER"], discount_limit_pct=Decimal("20.00"))

    # Create quotation
    q = Quotation.objects.create(
        title="عرض فحص",
        customer=quote_setup["customer"],
        created_by=sales_rep,
    )
    v1 = QuotationVersion.objects.create(
        quotation=q,
        version_number=1,
        created_by=sales_rep,
        discount_pct=Decimal("12.00"),  # Exceeds rep's 5% limit!
    )
    QuotationLine.objects.create(
        version=v1,
        model=quote_setup["model"],
        quantity=2,
        unit_price=Decimal("15000.00"),
        total_price=Decimal("30000.00"),
    )

    client_rep = auth_client(sales_rep)

    # Adding a line evaluates approval requirement
    line_r = client_rep.post(
        "/api/v1/quotation-lines/",
        {
            "version": str(v1.id),
            "model": str(quote_setup["model"].id),
            "quantity": 1,
            "unit_price": "10000.00",
            "discount_pct": "0.00",
        },
        format="json",
    )
    assert line_r.status_code == 201

    v1.refresh_from_db()
    assert v1.requires_approval is True
    assert v1.status == QuotationVersion.Status.PENDING_APPROVAL

    # 1. Sales rep CANNOT self-approve (Spec §9, ADR-032)
    assert client_rep.post(f"/api/v1/quotation-versions/{v1.id}/approve/").status_code == 403

    # 2. Sales manager approves it
    client_mgr = auth_client(sales_mgr)
    appr_res = client_mgr.post(f"/api/v1/quotation-versions/{v1.id}/approve/")
    assert appr_res.status_code == 200
    assert appr_res.data["status"] == "APPROVED"
    assert appr_res.data["snapshot"] is not None
    assert appr_res.data["snapshot"]["quotation_number"] == q.quotation_number


def test_approved_quotation_version_is_immutable(quote_setup, make_user, auth_client):
    sales_rep = make_user("rep@x.com", roles=["SALES_REP"])
    q = Quotation.objects.create(title="عرض معتمد", customer=quote_setup["customer"])
    v1 = QuotationVersion.objects.create(
        quotation=q, version_number=1, status=QuotationVersion.Status.APPROVED
    )
    line = QuotationLine.objects.create(
        version=v1,
        model=quote_setup["model"],
        quantity=1,
        unit_price=Decimal("20000.00"),
        total_price=Decimal("20000.00"),
    )

    client = auth_client(sales_rep)
    # Attempting to delete or edit lines on an approved version must fail with 422
    del_res = client.delete(f"/api/v1/quotation-lines/{line.id}/")
    assert del_res.status_code == 422
    assert "Cannot modify lines of an approved" in del_res.data["error"]["message"]
