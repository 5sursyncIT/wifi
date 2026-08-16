from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.crypto import get_random_string

# Internal roles of cahier des charges §7. "Citoyen/Visiteur" is not an internal
# role and is therefore absent. Permissions are attached from Phase 2 onwards,
# once the business models they apply to exist.
INTERNAL_ROLES = (
    "superadmin",
    "admin_ville",
    "exploitant_reseau",
    "responsable_commercial",
    "responsable_financier",
    "agent_support",
    "auditeur",
    "partenaire",
)


class Command(BaseCommand):
    help = "Create reproducible demonstration data. Never runs in production."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if settings.ENVIRONMENT == "production":
            raise CommandError(
                "Refusing to seed demonstration data in production "
                "(cahier des charges §1 rule 18, §21)."
            )

        groups = {}
        created = 0
        for role in INTERNAL_ROLES:
            groups[role], was_created = Group.objects.get_or_create(name=role)
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(f"Roles: {len(INTERNAL_ROLES)} present ({created} created).")
        )

        # Internal accounts exist for local development only (§21). Their passwords
        # are generated per run and printed once — never stored in the repository.
        if settings.ENVIRONMENT != "local":
            self.stdout.write(
                f"Environment is '{settings.ENVIRONMENT}': no demonstration account created."
            )
            return

        self._create_local_accounts(groups)

    def _create_local_accounts(self, groups: dict[str, Group]) -> None:
        user_model = get_user_model()
        for role, group in groups.items():
            username = f"demo_{role}"
            user, was_created = user_model.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@demo.invalid",
                    "is_staff": True,
                    "is_superuser": role == "superadmin",
                },
            )
            user.groups.add(group)
            if was_created:
                password = get_random_string(16)
                user.set_password(password)
                user.save(update_fields=["password"])
                self.stdout.write(f"  {username} / {password}")
