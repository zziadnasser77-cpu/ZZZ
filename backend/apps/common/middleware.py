"""Request-scoped context (request id, acting user, client IP)."""

import contextvars
import ipaddress
import logging
import re
import uuid

from django.conf import settings

current_user_var = contextvars.ContextVar("current_user", default=None)
request_id_var = contextvars.ContextVar("request_id", default="-")
client_ip_var = contextvars.ContextVar("client_ip", default=None)

_SAFE_REQ_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")


def get_current_user():
    user = current_user_var.get()
    return user if getattr(user, "is_authenticated", False) else None


def _extract_request_id(request) -> str:
    raw = (request.headers.get("X-Request-ID") or "").strip()
    if raw and _SAFE_REQ_ID_RE.match(raw):
        return raw
    return uuid.uuid4().hex


def _valid_ip(candidate: str | None) -> str | None:
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


def _extract_client_ip(request) -> str | None:
    num_proxies = getattr(settings, "NUM_PROXIES", 0)
    if num_proxies > 0:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                idx = max(0, len(parts) - num_proxies)
                ip = _valid_ip(parts[idx])
                if ip:
                    return ip
    return _valid_ip(request.META.get("REMOTE_ADDR"))


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class RequestContextMiddleware:
    """Assigns a trace id per request and exposes it in X-Request-ID."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = _extract_request_id(request)
        ip = _extract_client_ip(request)
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
