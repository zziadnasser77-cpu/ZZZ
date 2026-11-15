from datetime import date

import pytest

from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.pricing.models import PriceList, PriceListItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog_setup():
    cat = Category.objects.create(code="US", name_ar="الموجات فوق الصوتية", name_en="Ultrasound")
    mfg = Manufacturer.objects.create(
        code="SONO", name_ar="سونوسكيب", name_en="SonoScape", is_primary_partner=True
    )
    prod = Product.objects.create(
        code="US-S22",
        name_ar="جهاز سونار ملون متقدم",
        name_en="Color Doppler Ultrasound System",
        category=cat,
        manufacturer=mfg,
    )
    model = ProductModel.objects.create(
        product=prod,
        model_code="S22-EXP",
        model_name="S22 Expert Edition",
        sku="SKU-US-S22-EXP",
        approval_status=ProductModel.ApprovalStatus.DRAFT,
    )
    pl = PriceList.objects.create(
        code="PL-2026-USD",
        name_ar="قائمة أسعار الأجهزة 2026",
        name_en="Main Equipment Price List 2026",
        currency="USD",
        effective_from=date(2026, 1, 1),
        is_default=True,
    )
    item = PriceListItem.objects.create(
        price_list=pl,
        model=model,
        base_price="35000.00",
        min_price="30000.00",
        cost_price="22000.00",
    )
    return {
        "category": cat,
        "manufacturer": mfg,
        "product": prod,
        "model": model,
        "price_list": pl,
        "item": item,
    }


def test_sales_rep_cannot_see_supplier_cost(catalog_setup, make_user, auth_client):
    sales_rep = make_user("rep@x.com", roles=["SALES_REP"])
    client = auth_client(sales_rep)

    res = client.get("/api/v1/price-list-items/")
    assert res.status_code == 200
    assert len(res.data["results"]) == 1
    data = res.data["results"][0]
    assert data["base_price"] == "35000.00"
    assert data["min_price"] == "30000.00"
    # Strict privacy check: cost_price and margin_pct MUST NOT be present
    assert "cost_price" not in data
    assert "margin_pct" not in data


def test_sales_manager_can_see_supplier_cost_and_margin(catalog_setup, make_user, auth_client):
    sales_mgr = make_user("mgr@x.com", roles=["SALES_MANAGER"])
    client = auth_client(sales_mgr)

    res = client.get("/api/v1/price-list-items/")
    assert res.status_code == 200
    data = res.data["results"][0]
    assert data["cost_price"] == "22000.00"
    assert data["margin_pct"] == 37.14  # (35000 - 22000) / 35000 * 100


def test_model_approval_flow(catalog_setup, make_user, auth_client):
    model = catalog_setup["model"]
    sales_rep = make_user("rep@x.com", roles=["SALES_REP"])

    # Sales rep cannot approve models
    assert auth_client(sales_rep).post(f"/api/v1/models/{model.id}/approve/").status_code == 403

    # General Manager has catalog.* including catalog.model.approve
    mgr = make_user("mgr_appr@x.com", roles=["GENERAL_MANAGER"])
    r = auth_client(mgr).post(f"/api/v1/models/{model.id}/approve/")
    assert r.status_code == 200
    assert r.data["approval_status"] == "APPROVED"
    assert r.data["approved_by_email"] == "mgr_appr@x.com"


def test_price_item_min_price_cannot_exceed_base_price(catalog_setup, make_user, auth_client):
    admin = make_user("admin@x.com", roles=["SYSTEM_ADMIN"])
    client = auth_client(admin)
    pl = catalog_setup["price_list"]
    prod = catalog_setup["product"]
    new_model = ProductModel.objects.create(
        product=prod,
        model_code="S22-PRO",
        model_name="S22 Pro",
        sku="SKU-US-S22-PRO",
    )

    res = client.post(
        "/api/v1/price-list-items/",
        {
            "price_list": str(pl.id),
            "model": str(new_model.id),
            "base_price": "20000.00",
            "min_price": "25000.00",
        },
        format="json",
    )
    assert res.status_code == 400
    assert "min_price" in res.data["error"]["details"]
