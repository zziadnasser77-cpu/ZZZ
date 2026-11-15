import pytest
from rest_framework.test import APIClient

from apps.identity_access.management.commands.seed_rbac import sync_rbac
from apps.identity_access.models import Role, User

PASSWORD = "Str0ng-Pass-123!"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    from django.core.cache import cache

    cache.clear()
    yield


@pytest.fixture
def rbac(db):
    sync_rbac()


@pytest.fixture
def make_user(rbac):
    def _make(email="u@example.com", roles=(), **kw):
        u = User.objects.create_user(email=email, password=PASSWORD, **kw)
        u.roles.set(Role.objects.filter(code__in=roles))
        return u

    return _make


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def auth_client(api):
    def _auth(user):
        r = api.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
        assert r.status_code == 200, r.content
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return api

    return _auth
