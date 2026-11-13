from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.common.middleware import current_user_var


class ContextJWTAuthentication(JWTAuthentication):
    """JWT auth that publishes the acting user to request context (for created_by/audit)."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            current_user_var.set(result[0])
        return result
