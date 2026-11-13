from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Permission, Role

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "codename", "module", "resource", "action"]


class RoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SlugRelatedField(
        source="permissions", many=True, slug_field="codename",
        queryset=Permission.objects.all(), required=False,
    )

    class Meta:
        model = Role
        fields = ["id", "code", "name_ar", "name_en", "is_system", "permission_codes"]
        read_only_fields = ["is_system"]


class UserSerializer(serializers.ModelSerializer):
    role_codes = serializers.SlugRelatedField(
        source="roles", many=True, slug_field="code", queryset=Role.objects.all(), required=False
    )
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "preferred_language", "is_active",
            "role_codes", "discount_limit_pct", "approval_limit_amount",
            "mfa_enabled", "last_login", "password",
        ]
        read_only_fields = ["mfa_enabled", "last_login"]

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value

    def create(self, validated):
        roles = validated.pop("roles", [])
        password = validated.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "Required."})
        user = User.objects.create_user(password=password, **validated)
        user.roles.set(roles)
        return user

    def update(self, instance, validated):
        roles = validated.pop("roles", None)
        password = validated.pop("password", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance


class MeSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    roles = serializers.SlugRelatedField(many=True, slug_field="code", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "preferred_language", "roles", "permissions", "mfa_enabled"]

    def get_permissions(self, obj):
        return sorted(obj.permission_codes())


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    otp = serializers.CharField(required=False, allow_blank=True)


class OtpSerializer(serializers.Serializer):
    otp = serializers.CharField()
