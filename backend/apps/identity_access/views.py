from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.decorators import method_decorator
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import log_event
from apps.common.exceptions import BusinessRuleViolation, build_error_payload

from . import services
from .models import Permission, Role
from .permissions import HasPermission
from .permissions_registry import FINANCIAL_APPROVAL_ACTIONS
from .serializers import (
    LoginSerializer,
    MeSerializer,
    MfaDisableSerializer,
    OtpSerializer,
    PasswordChangeSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserSerializer,
)

User = get_user_model()


def _enforce_role_grant_ceiling(actor: User, target_roles):
    """An actor cannot assign a role that holds permissions the actor does not possess,
    unless the actor has `identity.role.manage`."""
    if actor.has_perm_code("identity.role.manage"):
        return
    actor_perms = actor.permission_codes()
    for role in target_roles:
        role_perms = set(role.permissions.values_list("codename", flat=True))
        missing = role_perms - actor_perms
        if missing:
            raise PermissionDenied("Cannot grant a role containing permissions you do not hold.")


def _ensure_not_last_system_admin(user: User, new_roles=None, deactivating: bool = False):
    if not user.roles.filter(code="SYSTEM_ADMIN").exists():
        return
    losing_admin = deactivating or (
        new_roles is not None and not any(r.code == "SYSTEM_ADMIN" for r in new_roles)
    )
    if not losing_admin:
        return
    other_admins = (
        User.objects.filter(is_active=True, roles__code="SYSTEM_ADMIN").exclude(pk=user.pk).exists()
    )
    if not other_admins:
        raise BusinessRuleViolation("Cannot remove or deactivate the last active SYSTEM_ADMIN.")


# non_atomic: failed-login counters / lockout MUST persist even though the request errors out.
@method_decorator(transaction.non_atomic_requests, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get_authenticate_header(self, request):
        return "Bearer"  # so AuthenticationFailed maps to 401 (not 403)

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            user = services.authenticate_user(**s.validated_data)
        except (AuthenticationFailed, PermissionDenied) as exc:
            # Return (don't raise): raising makes DRF mark the transaction for rollback,
            # which must not discard failed-attempt counters / lockout state.
            headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else {}
            return Response(build_error_payload(exc), status=exc.status_code, headers=headers)
        return Response({**services.issue_tokens(user), "user": MeSerializer(user).data})


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        token = request.data.get("refresh", "")
        try:
            old = RefreshToken(token)
            user = User.objects.get(pk=old["user_id"], is_active=True)
            old.blacklist()
        except (TokenError, User.DoesNotExist, KeyError):
            return Response({"error": {"code": "invalid_token", "message": "Invalid token."}}, status=401)
        return Response(services.issue_tokens(user))


class LogoutView(APIView):
    """Accepts refresh token even if access token has expired so session is reliably revoked."""

    permission_classes = [AllowAny]

    def post(self, request):
        actor = request.user if getattr(request.user, "is_authenticated", False) else None
        raw = request.data.get("refresh", "")
        if raw:
            try:
                tok = RefreshToken(raw)
                if actor is None and "user_id" in tok:
                    actor = User.objects.filter(pk=tok["user_id"]).first()
                tok.blacklist()
            except TokenError:
                pass
        if actor is not None:
            log_event("auth.logout", actor=actor, entity=actor)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    def post(self, request):
        u = request.user
        s = PasswordChangeSerializer(data=request.data, context={"user": u})
        s.is_valid(raise_exception=True)
        if not u.check_password(s.validated_data["current_password"]):
            raise BusinessRuleViolation("Current password is incorrect.", code="invalid_password")
        u.set_password(s.validated_data["new_password"])
        u.save(update_fields=["password", "updated_at"])
        services.revoke_user_tokens(u)
        log_event("auth.password_changed", actor=u, entity=u, sensitive=True)
        return Response({"detail": "Password updated."})


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class MfaSetupView(APIView):
    def post(self, request):
        u = request.user
        if u.mfa_enabled:
            raise BusinessRuleViolation("MFA already enabled.")
        secret = u.new_mfa_secret()
        return Response({"secret": secret, "otpauth_uri": u.provisioning_uri()})


class MfaConfirmView(APIView):
    def post(self, request):
        s = OtpSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        u = request.user
        if not u.mfa_secret or not u.verify_otp(s.validated_data["otp"]):
            raise BusinessRuleViolation("Invalid code.", code="invalid_otp")
        u.mfa_enabled = True
        u.save(update_fields=["mfa_enabled"])
        log_event("auth.mfa_enabled", actor=u, entity=u, sensitive=True)
        return Response({"mfa_enabled": True})


class MfaDisableView(APIView):
    def post(self, request):
        s = MfaDisableSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        u = request.user
        pw = s.validated_data.get("password")
        if pw is not None and pw != "" and not u.check_password(pw):
            raise BusinessRuleViolation("Invalid password.", code="invalid_password")
        if not u.mfa_enabled or not u.verify_otp(s.validated_data["otp"]):
            raise BusinessRuleViolation("Invalid code.", code="invalid_otp")
        u.mfa_enabled = False
        u.mfa_secret = ""
        u.save(update_fields=["mfa_enabled", "mfa_secret"])
        log_event("auth.mfa_disabled", actor=u, entity=u, sensitive=True)
        return Response({"mfa_enabled": False})


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related("roles").order_by("email")
    serializer_class = UserSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "identity.user.view",
        "retrieve": "identity.user.view",
        "create": "identity.user.create",
        "update": "identity.user.edit",
        "partial_update": "identity.user.edit",
        "destroy": "identity.user.manage",
    }
    search_fields = ["email", "full_name"]
    filterset_fields = ["is_active"]

    def perform_create(self, serializer):
        roles = serializer.validated_data.get("roles", [])
        if roles:
            _enforce_role_grant_ceiling(self.request.user, roles)
        if (
            serializer.validated_data.get("discount_limit_pct") is not None
            or serializer.validated_data.get("approval_limit_amount") is not None
        ) and not self.request.user.has_perm_code("identity.user.manage"):
            raise PermissionDenied("Setting financial/approval limits requires identity.user.manage.")
        user = serializer.save()
        log_event(
            "user.created",
            entity=user,
            summary=user.email,
            changes={"roles": sorted(r.code for r in roles)},
            sensitive=bool(roles),
        )

    def perform_update(self, serializer):
        actor = self.request.user
        target = serializer.instance
        new_roles = serializer.validated_data.get("roles")
        before_roles = set(target.roles.values_list("code", flat=True))

        # Prevent self-escalation of roles or financial ceilings
        if target.pk == actor.pk:
            if new_roles is not None and {r.code for r in new_roles} != before_roles:
                raise PermissionDenied("Users cannot modify their own roles.")
            if (
                "discount_limit_pct" in serializer.validated_data
                or "approval_limit_amount" in serializer.validated_data
            ):
                raise PermissionDenied("Users cannot modify their own approval/discount limits.")
            if serializer.validated_data.get("is_active") is False:
                raise BusinessRuleViolation("Users cannot deactivate their own account.")

        if new_roles is not None and {r.code for r in new_roles} != before_roles:
            _enforce_role_grant_ceiling(actor, new_roles)
            _ensure_not_last_system_admin(target, new_roles=new_roles)

        if (
            (
                "discount_limit_pct" in serializer.validated_data
                and serializer.validated_data["discount_limit_pct"] != target.discount_limit_pct
            )
            or (
                "approval_limit_amount" in serializer.validated_data
                and serializer.validated_data["approval_limit_amount"] != target.approval_limit_amount
            )
        ) and not actor.has_perm_code("identity.user.manage"):
            raise PermissionDenied("Modifying financial/approval limits requires identity.user.manage.")

        if serializer.validated_data.get("is_active") is False and target.is_active:
            _ensure_not_last_system_admin(target, deactivating=True)

        before_state = {
            "is_active": target.is_active,
            "discount_limit_pct": str(target.discount_limit_pct)
            if target.discount_limit_pct is not None
            else None,
            "approval_limit_amount": str(target.approval_limit_amount)
            if target.approval_limit_amount is not None
            else None,
        }
        pw_changed = bool(serializer.validated_data.get("password"))

        user = serializer.save()
        after_roles = set(user.roles.values_list("code", flat=True))
        after_state = {
            "is_active": user.is_active,
            "discount_limit_pct": str(user.discount_limit_pct)
            if user.discount_limit_pct is not None
            else None,
            "approval_limit_amount": str(user.approval_limit_amount)
            if user.approval_limit_amount is not None
            else None,
        }

        if pw_changed or not user.is_active:
            services.revoke_user_tokens(user)

        changes: dict = {}
        if before_roles != after_roles:
            changes["roles_before"] = sorted(before_roles)
            changes["roles_after"] = sorted(after_roles)
        for k in before_state:
            if before_state[k] != after_state[k]:
                changes[k] = {"before": before_state[k], "after": after_state[k]}
        if pw_changed:
            changes["password_reset"] = True

        roles_changed = before_roles != after_roles
        sensitive = roles_changed or pw_changed or bool(changes)
        action = (
            "user.roles_changed"
            if roles_changed
            else ("user.password_reset" if pw_changed else "user.updated")
        )
        log_event(action, entity=user, changes=changes or None, sensitive=sensitive)

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise BusinessRuleViolation("Users cannot deactivate their own account.")
        _ensure_not_last_system_admin(instance, deactivating=True)
        # no hard deletes: deactivate (history & FK integrity)
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        services.revoke_user_tokens(instance)
        log_event("user.deactivated", entity=instance, sensitive=True)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").order_by("code")
    serializer_class = RoleSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "identity.role.view",
        "retrieve": "identity.role.view",
        "create": "identity.role.create",
        "update": "identity.role.edit",
        "partial_update": "identity.role.edit",
        "destroy": "identity.role.manage",
    }

    def _validate_role_permissions(self, role_code: str, perms):
        if perms is None:
            return
        actor = self.request.user
        perm_codes = {p.codename for p in perms}
        if role_code == "SYSTEM_ADMIN" and any(
            c.endswith(tuple(f".{a}" for a in FINANCIAL_APPROVAL_ACTIONS)) for c in perm_codes
        ):
            raise BusinessRuleViolation(
                "SYSTEM_ADMIN cannot hold financial approve/post permissions (spec §9)."
            )
        if not actor.has_perm_code("identity.role.manage"):
            missing = perm_codes - actor.permission_codes()
            if missing:
                raise PermissionDenied("Cannot assign permissions you do not hold.")

    def perform_create(self, serializer):
        perms = serializer.validated_data.get("permissions", [])
        self._validate_role_permissions(serializer.validated_data.get("code", ""), perms)
        role = serializer.save()
        log_event("role.created", entity=role, sensitive=True)

    def perform_update(self, serializer):
        if (
            serializer.instance.is_system
            and "code" in serializer.validated_data
            and serializer.validated_data["code"] != serializer.instance.code
        ):
            raise BusinessRuleViolation("System role code cannot be changed.")
        perms = serializer.validated_data.get("permissions")
        self._validate_role_permissions(serializer.instance.code, perms)
        before = sorted(serializer.instance.permissions.values_list("codename", flat=True))
        role = serializer.save()
        after = sorted(role.permissions.values_list("codename", flat=True))
        log_event(
            "role.permissions_changed",
            entity=role,
            sensitive=True,
            changes={"before": before, "after": after},
        )

    def perform_destroy(self, instance):
        if instance.is_system:
            raise BusinessRuleViolation("System roles cannot be deleted.")
        if instance.users.exists():
            raise BusinessRuleViolation("Role is assigned to users.")
        log_event("role.deleted", entity=instance, sensitive=True)
        instance.delete()


class PermissionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [HasPermission]
    permission_map = {"list": "identity.role.view"}
    pagination_class = None
