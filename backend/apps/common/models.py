import uuid

from django.conf import settings
from django.db import models

from .middleware import get_current_user


class BaseModel(models.Model):
    """Stable UUID pk + created/updated by/at (spec §7.1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
        on_delete=models.PROTECT, related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
        on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user is not None:
            if self._state.adding and self.created_by_id is None:
                self.created_by = user
            self.updated_by = user
            uf = kwargs.get("update_fields")
            if uf is not None:
                kwargs["update_fields"] = list(set(uf) | {"updated_by", "updated_at"})
        super().save(*args, **kwargs)


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError(f"{self.model.__name__} is append-only")

    def delete(self):
        raise PermissionError(f"{self.model.__name__} is append-only")


class ImmutableModel(models.Model):
    """Append-only record (audit events, posted ledger rows). Enforced in app AND in DB triggers."""

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError(f"{type(self).__name__} is append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError(f"{type(self).__name__} is append-only")
