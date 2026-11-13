import uuid

from django.conf import settings
from django.db import models

from apps.common.models import ImmutableModel


class AuditEvent(ImmutableModel):
    """Append-only audit trail (ADR-037). UPDATE/DELETE blocked in app and by DB trigger (migration 0002)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=80, db_index=True)
    entity_type = models.CharField(max_length=80, blank=True, db_index=True)
    entity_id = models.CharField(max_length=64, blank=True, db_index=True)
    summary = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(null=True, blank=True)
    sensitive = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id", "-occurred_at"])]
