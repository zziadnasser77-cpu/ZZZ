import pytest

from apps.audit.models import AuditEvent
from apps.crm.models import Customer

pytestmark = pytest.mark.django_db


def test_customer_creation_generates_number_and_audits(make_user, auth_client):
    sales_rep = make_user("sales1@x.com", roles=["SALES_REP"])
    client = auth_client(sales_rep)

    data = {
        "customer_type": "HOSPITAL",
        "legal_name_ar": "مستشفى الأمل التخصصي",
        "governorate": "صنعاء",
        "phone": "+9671234567",
        "status": "ACTIVE",
    }
    res = client.post("/api/v1/customers/", data, format="json")
    assert res.status_code == 201, res.data
    assert res.data["customer_number"].startswith("CUST-")
    assert res.data["legal_name_ar"] == "مستشفى الأمل التخصصي"

    # Audit event logged
    assert AuditEvent.objects.filter(action="crm.customer_created").exists()


def test_contact_management_and_primary_switch(make_user, auth_client):
    sales_rep = make_user("sales1@x.com", roles=["SALES_REP"])
    client = auth_client(sales_rep)

    cust = Customer.objects.create(legal_name_ar="مستشفى الثورة")

    c1 = client.post(
        "/api/v1/contacts/",
        {"customer": str(cust.id), "name": "د. أحمد علي", "role": "MANAGEMENT", "is_primary": True},
        format="json",
    ).data
    assert c1["is_primary"] is True

    c2 = client.post(
        "/api/v1/contacts/",
        {"customer": str(cust.id), "name": "م. سامي طاهر", "role": "BIOMEDICAL_ENGINEER", "is_primary": True},
        format="json",
    ).data
    assert c2["is_primary"] is True

    # Check that previous contact is no longer primary
    cust_res = client.get(f"/api/v1/customers/{cust.id}/")
    assert cust_res.data["primary_contact"]["name"] == "م. سامي طاهر"


def test_opportunity_stage_changes_audited_as_sensitive_on_close(make_user, auth_client):
    sales_rep = make_user("sales1@x.com", roles=["SALES_REP"])
    client = auth_client(sales_rep)

    cust = Customer.objects.create(legal_name_ar="مركز القلب")
    opp_data = {
        "title": "توريد جهاز موجات فوق صوتية دوبلر ملون",
        "customer": str(cust.id),
        "stage": "DISCOVERY",
        "expected_value": "45000.00",
        "currency": "USD",
        "probability_pct": 60,
    }
    r = client.post("/api/v1/opportunities/", opp_data, format="json")
    assert r.status_code == 201
    opp_id = r.data["id"]

    # Close opportunity as WON
    patch_res = client.patch(f"/api/v1/opportunities/{opp_id}/", {"stage": "WON"}, format="json")
    assert patch_res.status_code == 200

    ev = AuditEvent.objects.get(action="crm.opportunity_updated")
    assert ev.sensitive is True
    assert ev.changes["stage"]["after"] == "WON"
