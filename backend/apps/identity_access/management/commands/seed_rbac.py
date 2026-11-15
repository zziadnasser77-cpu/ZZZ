from django.core.management.base import BaseCommand
from django.db import transaction

from apps.identity_access import permissions_registry as reg
from apps.identity_access.models import Permission, Role


def sync_rbac(reset_role_perms: bool = False):
    """Idempotent: sync Permission rows from the registry; create template roles.
    Existing roles keep customised permissions unless reset_role_perms=True."""
    for code in reg.all_codenames():
        module, resource, action = code.split(".")
        Permission.objects.get_or_create(
            codename=code, defaults={"module": module, "resource": resource, "action": action}
        )
    Permission.objects.exclude(codename__in=reg.all_codenames()).delete()
    for rc, t in reg.ROLE_TEMPLATES.items():
        role, created = Role.objects.get_or_create(
            code=rc, defaults={"name_ar": t["name_ar"], "name_en": t["name_en"], "is_system": True}
        )
        if created or reset_role_perms:
            role.permissions.set(Permission.objects.filter(codename__in=reg.expand(t["perms"])))


class Command(BaseCommand):
    help = "Seed permissions and default role templates (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-roles", action="store_true", help="Overwrite role permissions with templates"
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        sync_rbac(opts["reset_roles"])
        self.stdout.write(
            self.style.SUCCESS(f"{Permission.objects.count()} permissions, {Role.objects.count()} roles.")
        )
