from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models, transaction
from django.utils import timezone

from apps.common.models import BaseModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class Permission(models.Model):
    codename = models.CharField(max_length=100, unique=True)
    module = models.CharField(max_length=50, db_index=True)
    resource = models.CharField(max_length=50)
    action = models.CharField(max_length=20)

    class Meta:
        ordering = ["codename"]

    def __str__(self):
        return self.codename


class Role(BaseModel):
    code = models.CharField(max_length=50, unique=True)
    name_ar = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    is_system = models.BooleanField(default=False, help_text="Seeded template role; cannot be deleted.")
    permissions = models.ManyToManyField(Permission, blank=True, related_name="roles")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class User(AbstractBaseUser, BaseModel):
    """Platform user. Superuser is a technical flag only — it never bypasses RBAC checks."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    preferred_language = models.CharField(
        max_length=5, default="ar", choices=[("ar", "العربية"), ("en", "English")]
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="users")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Approval / value limits (ADR-032): per-user ceilings; None = no authority.
    discount_limit_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    approval_limit_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    # Lockout (ADR-037)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    # MFA TOTP
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    # --- permissions ---
    def permission_codes(self) -> set[str]:
        cached = getattr(self, "_perm_cache", None)
        if cached is None:
            cached = set(
                Permission.objects.filter(roles__users=self, roles__users__is_active=True).values_list(
                    "codename", flat=True
                )
            )
            self._perm_cache = cached
        return cached

    def invalidate_perm_cache(self):
        if hasattr(self, "_perm_cache"):
            delattr(self, "_perm_cache")

    def has_perm_code(self, codename: str) -> bool:
        return self.is_active and codename in self.permission_codes()

    # Django admin compatibility (admin allowed only for staff superusers)
    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser

    # --- lockout ---
    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self):
        with transaction.atomic():
            locked = User.objects.select_for_update().get(pk=self.pk)
            locked.failed_login_attempts += 1
            if locked.failed_login_attempts >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
                locked.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                locked.failed_login_attempts = 0
            locked.save(update_fields=["failed_login_attempts", "locked_until"])
            self.failed_login_attempts = locked.failed_login_attempts
            self.locked_until = locked.locked_until

    def reset_failed_logins(self):
        if self.failed_login_attempts or self.locked_until:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=["failed_login_attempts", "locked_until"])

    # --- MFA ---
    def new_mfa_secret(self) -> str:
        self.mfa_secret = pyotp.random_base32()
        self.save(update_fields=["mfa_secret"])
        return self.mfa_secret

    def provisioning_uri(self) -> str:
        return pyotp.TOTP(self.mfa_secret).provisioning_uri(name=self.email, issuer_name=settings.MFA_ISSUER)

    def verify_otp(self, code: str) -> bool:
        return bool(self.mfa_secret) and pyotp.TOTP(self.mfa_secret).verify(str(code), valid_window=1)
