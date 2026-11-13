import pytest

from apps.audit.models import AuditEvent
from apps.audit.services import log_event
from apps.identity_access.models import Role
from apps.organization_settings.models import next_document_number

pytestmark = pytest.mark.django_db


def test_sales_rep_cannot_list_users(make_user, auth_client):
    c = auth_client(make_user("s@x.com", roles=["SALES_REP"]))
    assert c.get("/api/v1/users/").status_code == 403


def test_admin_can_manage_users_and_actions_are_audited(make_user, auth_client):
    c = auth_client(make_user("admin@x.com", roles=["SYSTEM_ADMIN"]))
    r = c.post("/api/v1/users/", {"email": "new@x.com", "password": "An0ther-Str0ng-Pass!",
                                 "role_codes": ["SALES_REP"]}, format="json")
    assert r.status_code == 201, r.data
    assert AuditEvent.objects.filter(action="user.created").exists()
    uid = r.data["id"]
    c.patch(f"/api/v1/users/{uid}/", {"role_codes": ["ACCOUNTANT"]}, format="json")
    ev = AuditEvent.objects.get(action="user.roles_changed")
    assert ev.sensitive and ev.changes["roles_after"] == ["ACCOUNTANT"]


def test_system_admin_has_no_financial_approval(make_user):
    u = make_user("admin@x.com", roles=["SYSTEM_ADMIN"])
    assert not any(p.endswith((".approve", ".post")) for p in u.permission_codes())


def test_superuser_flag_does_not_bypass_rbac(make_user, auth_client):
    u = make_user("root@x.com", is_superuser=True)
    assert auth_client(u).get("/api/v1/users/").status_code == 403


def test_system_roles_cannot_be_deleted(make_user, auth_client):
    c = auth_client(make_user("admin@x.com", roles=["SYSTEM_ADMIN"]))
    rid = Role.objects.get(code="SALES_REP").id
    assert c.delete(f"/api/v1/roles/{rid}/").status_code == 422


def test_audit_is_append_only():
    ev = log_event("t.test", summary="x")
    ev.summary = "tampered"
    with pytest.raises(PermissionError):
        ev.save()
    with pytest.raises(PermissionError):
        ev.delete()
    with pytest.raises(PermissionError):
        AuditEvent.objects.all().delete()


def test_audit_is_blocked_at_database_level():
    from django.db import connection, transaction
    from django.db.utils import ProgrammingError

    ev = log_event("t.db", summary="x")
    with pytest.raises(ProgrammingError), transaction.atomic(), connection.cursor() as cur:
        cur.execute("UPDATE audit_auditevent SET summary='tampered' WHERE id=%s", [ev.id])
    with pytest.raises(ProgrammingError), transaction.atomic(), connection.cursor() as cur:
        cur.execute("DELETE FROM audit_auditevent WHERE id=%s", [ev.id])


def test_document_numbering_sequential():
    a = next_document_number("quotation", prefix="QT")
    b = next_document_number("quotation", prefix="QT")
    assert a.endswith("000001") and b.endswith("000002")
