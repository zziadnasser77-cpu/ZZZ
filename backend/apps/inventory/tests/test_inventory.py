from decimal import Decimal

import pytest

from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.inventory.models import (
    CustodyRecord,
    Location,
    OwnershipRecord,
    SerialAsset,
    StockCount,
    StockCountItem,
    StockMovement,
)
from apps.inventory.services import (
    get_stock_balance,
    post_stock_count,
    record_stock_movement,
    transfer_custody,
    transfer_ownership,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def inv_setup():
    wh = Location.objects.create(
        code="WH-MAIN", name_ar="المستودع الرئيسي", location_type=Location.LocationType.WAREHOUSE
    )
    transit = Location.objects.create(
        code="LOC-TRANSIT", name_ar="في العبور", location_type=Location.LocationType.IN_TRANSIT
    )
    cust_loc = Location.objects.create(
        code="CUST-HOSP",
        name_ar="مستشفى الثورة (موقع العميل)",
        location_type=Location.LocationType.CUSTOMER_SITE,
    )

    cat = Category.objects.create(code="US", name_ar="سونار", name_en="Ultrasound")
    mfg = Manufacturer.objects.create(code="SONO", name_ar="سونوسكيب", name_en="SonoScape")
    prod = Product.objects.create(
        code="US-E2",
        name_ar="جهاز سونار محمول",
        name_en="Portable Ultrasound",
        category=cat,
        manufacturer=mfg,
    )
    model = ProductModel.objects.create(
        product=prod, model_code="E2-PRO", model_name="E2 Pro Portable", sku="SKU-US-E2P"
    )

    asset = SerialAsset.objects.create(
        serial_number="SN-E2-2026-001",
        model=model,
        current_location=wh,
        current_owner="SMSES Local Partner",
        current_custodian="Main Warehouse Storage",
    )
    return {"wh": wh, "transit": transit, "cust_loc": cust_loc, "model": model, "asset": asset}


def test_ownership_vs_custody_vs_location_separation(inv_setup):
    """Moving an asset to a customer site or engineer custody MUST NOT transfer legal ownership. Spec §1.1, §5.8."""
    asset = inv_setup["asset"]
    wh = inv_setup["wh"]
    cust_loc = inv_setup["cust_loc"]

    # 1. Initial state: Owned by local company, in warehouse
    transfer_ownership(
        asset,
        owner_type=OwnershipRecord.OwnerType.LOCAL_COMPANY,
        owner_name="SMSES Partner",
        proof_document_ref="PO-001",
    )
    transfer_custody(
        asset,
        custodian_type=CustodyRecord.CustodianType.USER,
        custodian_name="أمين المستودع",
        purpose="Storage",
    )

    # 2. Asset moved to customer site for DEMO / Trial
    record_stock_movement(
        movement_type=StockMovement.MovementType.TRANSFER,
        model=asset.model,
        asset=asset,
        from_location=wh,
        to_location=cust_loc,
        quantity=1,
    )
    transfer_custody(
        asset,
        custodian_type=CustodyRecord.CustodianType.CUSTOMER,
        custodian_name="مستشفى الثورة",
        purpose="Trial / Demo (أمانة للتجربة)",
    )

    asset.refresh_from_db()
    # Location changed
    assert asset.current_location == cust_loc
    # Custodian changed
    assert "مستشفى الثورة" in asset.current_custodian
    # Legal ownership is STILL the local company!
    assert asset.current_owner == "SMSES Partner"
    assert (
        asset.ownership_history.filter(is_current=True).first().owner_type
        == OwnershipRecord.OwnerType.LOCAL_COMPANY
    )


def test_stock_movement_ledger_and_balance_derivation(inv_setup):
    """Stock balance is dynamically derived from movements; movements are append-only. Spec §1.1, §5.8."""
    wh = inv_setup["wh"]
    model = inv_setup["model"]

    # 1. Receipt movement (+10)
    m1 = record_stock_movement(
        movement_type=StockMovement.MovementType.RECEIPT,
        model=model,
        quantity=10,
        to_location=wh,
        unit_cost=Decimal("5000.00"),
    )
    assert get_stock_balance(model, wh) == 10

    # 2. Sale dispatch (-3)
    record_stock_movement(
        movement_type=StockMovement.MovementType.SALE_DISPATCH,
        model=model,
        quantity=3,
        from_location=wh,
    )
    assert get_stock_balance(model, wh) == 7

    # 3. Immutability check: posted movements cannot be deleted or updated
    with pytest.raises(PermissionError):
        m1.quantity = 15
        m1.save()

    with pytest.raises(PermissionError):
        m1.delete()


def test_stock_count_and_automatic_adjustment_posting(inv_setup, make_user):
    wh = inv_setup["wh"]
    model = inv_setup["model"]
    admin = make_user("admin@x.com", roles=["SYSTEM_ADMIN"])

    # Initial stock balance = 5
    record_stock_movement(
        movement_type=StockMovement.MovementType.RECEIPT,
        model=model,
        quantity=5,
        to_location=wh,
    )

    # Physical count finds only 4 (shortage of -1)
    from datetime import date

    sc = StockCount.objects.create(
        location=wh, count_date=date(2026, 11, 1), status=StockCount.Status.APPROVED
    )
    StockCountItem.objects.create(
        stock_count=sc,
        model=model,
        system_quantity=5,
        counted_quantity=4,
    )

    post_stock_count(sc, admin)
    sc.refresh_from_db()
    assert sc.status == StockCount.Status.POSTED

    # Stock balance updated to 4
    assert get_stock_balance(model, wh) == 4
    # Adjustment movement logged
    assert StockMovement.objects.filter(movement_type=StockMovement.MovementType.ADJUSTMENT).exists()
