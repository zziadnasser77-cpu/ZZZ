import pytest

from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.procurement.models import Supplier

pytestmark = pytest.mark.django_db


@pytest.fixture
def supplier_setup():
    sup = Supplier.objects.create(
        code="SUP-CHINA-OEM",
        name_ar="شركة شنتشن للأجهزة الطبية",
        name_en="Shenzhen Medical Co., Ltd.",
        country="China",
        currency="USD",
        is_primary_partner=True,
    )
    cat = Category.objects.create(code="MON", name_ar="مراقبة المرضى", name_en="Patient Monitoring")
    mfg = Manufacturer.objects.create(code="SZ-MED", name_ar="شنتشن ميديكال", name_en="Shenzhen Med")
    prod = Product.objects.create(
        code="PM-V8",
        name_ar="مونيتور مريض متعدد المعايير",
        name_en="Multi-para Monitor",
        category=cat,
        manufacturer=mfg,
    )
    model = ProductModel.objects.create(
        product=prod, model_code="V8-ICU", model_name="V8 ICU Monitor", sku="SKU-PM-V8-ICU"
    )
    return {"supplier": sup, "model": model}


def test_supplier_order_creation_and_pi_confirmation(supplier_setup, make_user, auth_client):
    proc_mgr = make_user("proc_mgr@x.com", roles=["PROCUREMENT_MANAGER"])
    client = auth_client(proc_mgr)
    sup = supplier_setup["supplier"]
    model = supplier_setup["model"]

    # 1. Create Supplier Order
    po_res = client.post(
        "/api/v1/supplier-orders/",
        {
            "supplier": str(sup.id),
            "procurement_model": "DIRECT_STOCK",
            "currency": "USD",
            "shipping_port": "Shenzhen Port",
            "destination_port": "Aden Port",
            "freight_payer": "LOCAL_PARTNER",
        },
        format="json",
    )
    assert po_res.status_code == 201, po_res.data
    po_id = po_res.data["id"]
    po_num = po_res.data["order_number"]
    assert po_num.startswith("PO-")

    # 2. Add line
    line_res = client.post(
        "/api/v1/supplier-order-lines/",
        {
            "order": str(po_id),
            "model": str(model.id),
            "quantity": 5,
            "unit_cost": "1800.00",
            "total_cost": "9000.00",
        },
        format="json",
    )
    assert line_res.status_code == 201

    # 3. Confirm Supplier PI
    conf_res = client.post(
        f"/api/v1/supplier-orders/{po_id}/confirm-pi/",
        {"supplier_pi_reference": "PI-SZ-2026-8899"},
        format="json",
    )
    assert conf_res.status_code == 200
    assert conf_res.data["status"] == "CONFIRMED_BY_SUPPLIER"
    assert conf_res.data["supplier_pi_reference"] == "PI-SZ-2026-8899"
