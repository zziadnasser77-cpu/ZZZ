import pyotp
import pytest

from apps.audit.models import AuditEvent
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_login_success_and_me(make_user, api):
    make_user("a@x.com", roles=["SYSTEM_ADMIN"])
    r = api.post("/api/v1/auth/login/", {"email": "a@x.com", "password": PASSWORD}, format="json")
    assert r.status_code == 200 and "access" in r.data
    assert "identity.user.view" in r.data["user"]["permissions"]
    assert AuditEvent.objects.filter(action="auth.login").exists()


def test_login_wrong_password_generic_error(make_user, api):
    make_user("a@x.com")
    r = api.post("/api/v1/auth/login/", {"email": "a@x.com", "password": "nope"}, format="json")
    assert r.status_code == 401
    assert r.data["error"]["trace_id"]


def test_lockout_persists_after_failures(make_user, api, settings):
    settings.LOGIN_MAX_FAILED_ATTEMPTS = 3
    u = make_user("a@x.com")
    for _ in range(3):
        api.post("/api/v1/auth/login/", {"email": "a@x.com", "password": "bad"}, format="json")
    u.refresh_from_db()
    assert u.is_locked
    r = api.post("/api/v1/auth/login/", {"email": "a@x.com", "password": PASSWORD}, format="json")
    assert r.status_code == 401  # locked even with the right password


def test_mfa_flow(make_user, auth_client, api):
    u = make_user("a@x.com")
    c = auth_client(u)
    secret = c.post("/api/v1/auth/mfa/setup/").data["secret"]
    assert (
        c.post("/api/v1/auth/mfa/confirm/", {"otp": pyotp.TOTP(secret).now()}, format="json").status_code
        == 200
    )
    c.credentials()
    r = c.post("/api/v1/auth/login/", {"email": "a@x.com", "password": PASSWORD}, format="json")
    assert r.status_code == 403 and r.data["error"]["code"] == "mfa_required"
    r = c.post(
        "/api/v1/auth/login/",
        {"email": "a@x.com", "password": PASSWORD, "otp": pyotp.TOTP(secret).now()},
        format="json",
    )
    assert r.status_code == 200


def test_refresh_rotation_and_logout(make_user, api):
    make_user("a@x.com")
    tok = api.post("/api/v1/auth/login/", {"email": "a@x.com", "password": PASSWORD}, format="json").data
    r = api.post("/api/v1/auth/refresh/", {"refresh": tok["refresh"]}, format="json")
    assert r.status_code == 200
    # old refresh token is blacklisted
    assert api.post("/api/v1/auth/refresh/", {"refresh": tok["refresh"]}, format="json").status_code == 401


def test_logout_revokes_refresh_without_access_token(make_user, api):
    make_user("a@x.com")
    tok = api.post("/api/v1/auth/login/", {"email": "a@x.com", "password": PASSWORD}, format="json").data
    # Simulate expired/missing access token on logout
    r = api.post("/api/v1/auth/logout/", {"refresh": tok["refresh"]}, format="json")
    assert r.status_code == 204
    assert api.post("/api/v1/auth/refresh/", {"refresh": tok["refresh"]}, format="json").status_code == 401


def test_password_change_revokes_existing_tokens(make_user, auth_client, api):
    u = make_user("a@x.com")
    tok = api.post("/api/v1/auth/login/", {"email": "a@x.com", "password": PASSWORD}, format="json").data
    c = auth_client(u)
    r = c.post(
        "/api/v1/auth/password/",
        {"current_password": PASSWORD, "new_password": "BrandNew-Strong-Pass-99!"},
        format="json",
    )
    assert r.status_code == 200
    assert api.post("/api/v1/auth/refresh/", {"refresh": tok["refresh"]}, format="json").status_code == 401


def test_oversized_request_id_and_malformed_xff_do_not_500(make_user, api):
    make_user("a@x.com")
    r = api.post(
        "/api/v1/auth/login/",
        {"email": "a@x.com", "password": PASSWORD},
        format="json",
        HTTP_X_REQUEST_ID="x" * 200,
        HTTP_X_FORWARDED_FOR="not-an-ip-address",
    )
    assert r.status_code == 200
    assert len(r["X-Request-ID"]) == 32


def test_xff_spoofing_cannot_bypass_login_throttle(make_user, api):
    make_user("a@x.com")
    codes = [
        api.post(
            "/api/v1/auth/login/",
            {"email": "nobody@x.com", "password": "wrong"},
            format="json",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{i}",
        ).status_code
        for i in range(13)
    ]
    assert 429 in codes
