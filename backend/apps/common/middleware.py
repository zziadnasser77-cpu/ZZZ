"""Request-scoped context (request id, acting user, client IP)."""
import contextvars
import logging
import uuid

current_user_var = contextvars.ContextVar("current_user", default=None)
request_id_var = contextvars.ContextVar("request_id", default="-")
client_ip_var = contextvars.ContextVar("client_ip", default=None)


def get_current_user():
    user = current_user_var.get()
    return user if getattr(user, "is_authenticated", False) else None


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class RequestContextMiddleware:
    """Assigns a trace id per request and exposes it in X-Request-ID."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
        tokens = (request_id_var.set(rid), client_ip_var.set(ip), current_user_var.set(None))
        request.request_id = rid
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(tokens[0])
            client_ip_var.reset(tokens[1])
            current_user_var.reset(tokens[2])
        response["X-Request-ID"] = rid
        return response
