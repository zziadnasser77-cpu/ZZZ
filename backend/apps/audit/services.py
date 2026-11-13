from apps.common.middleware import client_ip_var, get_current_user, request_id_var

from .models import AuditEvent


def log_event(action, *, actor=None, entity=None, entity_type="", entity_id="", summary="",
              changes=None, sensitive=False) -> AuditEvent:
    actor = actor or get_current_user()
    if entity is not None:
        entity_type = entity_type or entity._meta.label_lower
        entity_id = entity_id or str(entity.pk)
        summary = summary or str(entity)[:300]
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action, entity_type=entity_type, entity_id=entity_id, summary=summary[:300],
        changes=changes, sensitive=sensitive,
        ip_address=client_ip_var.get(), request_id=request_id_var.get(),
    )
