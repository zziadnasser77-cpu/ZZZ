import pytest

from apps.procurement.models import Supplier, SupplierOrder
from apps.shipments.models import ShipmentDocument

pytestmark = pytest.mark.django_db


@pytest.fixture
def shipment_setup():
    sup = Supplier.objects.create(code="SUP-CHINA", name_ar="المورد الصيني", name_en="China Supplier")
    po = SupplierOrder.objects.create(supplier=sup)
    return {"supplier": sup, "po": po}


def test_shipment_creation_and_status_tracking(shipment_setup, make_user, auth_client):
    logistics = make_user("logistics@x.com", roles=["LOGISTICS_OFFICER"])
    client = auth_client(logistics)
    po = shipment_setup["po"]

    # 1. Create shipment
    res = client.post(
        "/api/v1/shipments/",
        {
            "supplier_order": str(po.id),
            "carrier_name": "COSCO Shipping Lines",
            "tracking_number": "COSU62839102",
            "shipping_method": "SEA_FREIGHT",
            "origin_port": "Shenzhen Port",
            "destination_port": "Aden Port",
            "status": "DISPATCHED",
        },
        format="json",
    )
    assert res.status_code == 201, res.data
    shp_id = res.data["id"]
    assert res.data["shipment_number"].startswith("SHP-")

    # 2. Add Bill of Lading document
    doc_res = client.post(
        "/api/v1/shipment-documents/",
        {
            "shipment": str(shp_id),
            "doc_type": "BILL_OF_LADING",
            "document_number": "BL-SZ-2026-901",
            "file_url": "https://storage.smses.med/docs/bl_901.pdf",
        },
        format="json",
    )
    assert doc_res.status_code == 201
    assert ShipmentDocument.objects.filter(document_number="BL-SZ-2026-901").exists()

    # 3. Update status to PORT_ARRIVAL
    status_res = client.post(
        f"/api/v1/shipments/{shp_id}/update-status/",
        {
            "status": "PORT_ARRIVAL",
            "location": "Aden Container Terminal",
            "description": "Vessel berthed successfully",
        },
        format="json",
    )
    assert status_res.status_code == 200
    assert status_res.data["status"] == "PORT_ARRIVAL"
    assert len(status_res.data["events"]) == 1
