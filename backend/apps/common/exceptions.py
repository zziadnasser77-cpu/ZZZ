"""Unified structured API errors with trace id (spec §15)."""
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .middleware import request_id_var


class BusinessRuleViolation(exceptions.APIException):
    """Raised by services when a domain rule is violated (HTTP 409/422 semantic)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "business_rule_violation"
    default_detail = "Business rule violated."

    def __init__(self, detail=None, code=None):
        super().__init__(detail=detail, code=code or self.default_code)


def build_error_payload(exc) -> dict:
    code = getattr(exc, "default_code", "error")
    if isinstance(exc, exceptions.APIException):
        codes = exc.get_codes()
        code = codes if isinstance(codes, str) else "validation_error"
    return {
        "error": {
            "code": code,
            "message": _message(exc),
            "details": exc.detail if isinstance(exc, exceptions.ValidationError) else None,
            "trace_id": request_id_var.get(),
        }
    }


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(detail=exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    response = exception_handler(exc, context)
    if response is None:
        return None
    return Response(build_error_payload(exc), status=response.status_code, headers=dict(response.items()))



def _message(exc):
    if isinstance(exc, exceptions.ValidationError):
        return "Validation failed."
    detail = getattr(exc, "detail", None)
    return str(detail) if detail else "Error"
