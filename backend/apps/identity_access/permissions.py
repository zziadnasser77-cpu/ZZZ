"""DRF permission classes enforcing RBAC server-side (ADR-006)."""

from rest_framework.permissions import BasePermission


class HasPermission(BasePermission):
    """View declares `permission_map = {"list": "x.y.view", "create": "x.y.create", ...}`
    (action name or HTTP method name -> codename). Missing mapping => deny (secure by default)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        pmap = getattr(view, "permission_map", {})
        key = getattr(view, "action", None) or request.method.lower()
        code = pmap.get(key) or pmap.get(request.method.lower())
        return bool(code) and user.has_perm_code(code)


def require(codename: str):
    """Build a permission class for a single codename (APIView use)."""

    class _Require(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(u and u.is_authenticated and u.has_perm_code(codename))

    _Require.__name__ = f"Require[{codename}]"
    return _Require
