from decimal import Decimal

import pytest

from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.crm.models import Customer
from apps.quotations.models import CommercialModel, Quotation, QuotationLine, QuotationVersion
from apps.sales_orders.models import Deal, SalesOrder

pytestmark = pytest.mark.django_db


@pytest.fixture
def order_setup():
    cust = Customer.objects.create(legal_name_ar="مستشفى الأمل الأردني", governorate="حضرموت")
    cat = Category.objects.create(code="CT", name_ar="الأشعة المقطعية", name_en="CT Scan")
    mfg = Manufacturer.objects.create(code="CH-OEM", name_ar="المصنع الصيني", name_en="China OEM")
    prod = Product.objects.create(
        code="CT-64",
        name_ar="جهاز أشعة مقطعية 64 شريحة",
        name_en="64-Slice CT",
        category=cat,
        manufacturer=mfg,
    )
    model = ProductModel.objects.create(
        product=prod, model_code="CT-64P", model_name="CT 64 Pro", sku="SKU-CT-64P"
    )

    q = Quotation.objects.create(
        title="توريد جهاز أشعة مقطعية",
        customer=cust,
        commercial_model=CommercialModel.AGENCY,
        currency="USD",
    )
    v1 = QuotationVersion.objects.create(
        quotation=q,
        version_number=1,
        status=QuotationVersion.Status.ACCEPTED,
        subtotal=Decimal("180000.00"),
        total_amount=Decimal("180000.00"),
        delivery_terms="CIF Aden Port مع التركيب والتدريب",
        payment_terms="50% دفعة مقدمة، 50% بعد الفحص والتشغيل",
    )
    QuotationLine.objects.create(
        version=v1,
        model=model,
        description="جهاز أشعة مقطعية 64 شريحة مع محطة العمل",
        quantity=1,
        unit_price=Decimal("180000.00"),
        total_price=Decimal("180000.00"),
    )
    return {"customer": cust, "model": model, "quotation": q, "version": v1}


def test_convert_quotation_to_deal_and_sales_order(order_setup, make_user, auth_client):
    sales_rep = make_user("rep@x.com", roles=["SALES_REP"])
    client = auth_client(sales_rep)
    q = order_setup["quotation"]

    res = client.post("/api/v1/deals/from-quotation/", {"quotation_id": str(q.id)}, format="json")
    assert res.status_code == 201, res.data
    deal_id = res.data["id"]

    deal = Deal.objects.get(pk=deal_id)
    assert deal.deal_number.startswith("DEAL-")
    assert deal.commercial_model == CommercialModel.AGENCY
    assert deal.total_value == Decimal("180000.00")
    assert deal.customer == order_setup["customer"]

    # Sales order created automatically
    so = SalesOrder.objects.get(deal=deal)
    assert so.order_number.startswith("SO-")
    assert so.total_amount == Decimal("180000.00")
    assert so.lines.count() == 1
    assert so.lines.first().model == order_setup["model"]


def test_deal_legal_seller_and_invoicing_defaults(order_setup):
    cust = order_setup["customer"]
    deal_direct = Deal.objects.create(
        title="صفقة بيع مباشر",
        customer=cust,
        commercial_model=CommercialModel.DIRECT_SALE,
        total_value=Decimal("50000.00"),
    )
    assert "SMSES" in deal_direct.seller_of_record

    deal_agency = Deal.objects.create(
        title="صفقة وكالة",
        customer=cust,
        commercial_model=CommercialModel.AGENCY,
        total_value=Decimal("150000.00"),
    )
    assert "Chinese" in deal_agency.seller_of_record
