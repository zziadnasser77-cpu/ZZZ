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
from .serializers import (
    LoginSerializer,
    MeSerializer,
    OtpSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserSerializer,
)

User = get_user_model()


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
    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except TokenError:
            pass
        log_event("auth.logout", actor=request.user, entity=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        s = OtpSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        u = request.user
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
        "list": "identity.user.view", "retrieve": "identity.user.view",
        "create": "identity.user.create", "update": "identity.user.edit",
        "partial_update": "identity.user.edit", "destroy": "identity.user.manage",
    }
    search_fields = ["email", "full_name"]
    filterset_fields = ["is_active"]

    def perform_create(self, serializer):
        user = serializer.save()
        log_event("user.created", entity=user, summary=user.email)

    def perform_update(self, serializer):
        before = set(serializer.instance.roles.values_list("code", flat=True))
        user = serializer.save()
        after = set(user.roles.values_list("code", flat=True))
        changed = before != after or "password" in self.request.data
        log_event(
            "user.roles_changed" if changed else "user.updated", entity=user,
            changes={"roles_before": sorted(before), "roles_after": sorted(after)} if before != after else None,
            sensitive=changed,
        )

    def perform_destroy(self, instance):
        # no hard deletes: deactivate (history & FK integrity)
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        log_event("user.deactivated", entity=instance, sensitive=True)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").order_by("code")
    serializer_class = RoleSerializer
    permission_classes = [HasPermission]
    permission_map = {
        "list": "identity.role.view", "retrieve": "identity.role.view",
        "create": "identity.role.create", "update": "identity.role.edit",
        "partial_update": "identity.role.edit", "destroy": "identity.role.manage",
    }

    def perform_create(self, serializer):
        role = serializer.save()
        log_event("role.created", entity=role, sensitive=True)

    def perform_update(self, serializer):
        before = sorted(serializer.instance.permissions.values_list("codename", flat=True))
        role = serializer.save()
        after = sorted(role.permissions.values_list("codename", flat=True))
        log_event("role.permissions_changed", entity=role, sensitive=True,
                  changes={"before": before, "after": after})

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
