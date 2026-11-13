import getpass
import os

from django.core.management.base import BaseCommand, CommandError

from apps.identity_access.management.commands.seed_rbac import sync_rbac
from apps.identity_access.models import Role, User


class Command(BaseCommand):
    help = "Create the first SYSTEM_ADMIN user. Password via --password, SMSES_ADMIN_PASSWORD, or prompt."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password")
        parser.add_argument("--name", default="")

    def handle(self, *args, **opts):
        email = opts["email"].lower()
        if User.objects.filter(email=email).exists():
            raise CommandError(f"{email} already exists")
        pw = opts["password"] or os.environ.get("SMSES_ADMIN_PASSWORD") or getpass.getpass("Password: ")
        sync_rbac()
        user = User.objects.create_user(email=email, password=pw, full_name=opts["name"], is_staff=True)
        user.roles.add(Role.objects.get(code="SYSTEM_ADMIN"))
        self.stdout.write(self.style.SUCCESS(f"Created SYSTEM_ADMIN {email}"))
