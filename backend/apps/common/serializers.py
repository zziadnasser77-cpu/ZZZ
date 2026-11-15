"""Shared serializer helpers.

CostRestrictedMixin implements field-level security for supplier/acquisition costs
(spec §5.1, §9, acceptance criterion §16.1: a sales rep must never see supplier cost
without explicit permission). Fields are removed from *output* and ignored on *input*
for users lacking the permission, so cost cannot be read or tampered with.
"""

COST_PERMISSION = "pricing.cost.view"


class CostRestrictedMixin:
    cost_fields: tuple[str, ...] = ()
    cost_permission: str = COST_PERMISSION

    def _can_see_cost(self) -> bool:
        request = self.context.get("request") if hasattr(self, "context") else None
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.has_perm_code(self.cost_permission))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._can_see_cost():
            for f in self.cost_fields:
                data.pop(f, None)
        return data

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        if not self._can_see_cost():
            for f in self.cost_fields:
                validated.pop(f, None)
        return validated
