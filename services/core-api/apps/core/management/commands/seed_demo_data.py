from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.catalog.models import Plan, PlanVersion
from apps.network.models import Hotspot, Organization, Site, Zone

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

ORGANIZATION_NAME = "Ville de Dakar — Démonstration"

# Coordinates are real Dakar landmarks so the map is readable; everything else is
# fictional and labelled as such.
SITES: list[dict[str, Any]] = [
    {
        "name": "Place de l'Indépendance (démonstration)",
        "address": "Place de l'Indépendance, Dakar Plateau",
        "latitude": "14.667100",
        "longitude": "-17.437400",
        "zone": {
            "code": "demo-independance",
            "label": "Place de l'Indépendance",
            "access_mode": Zone.AccessMode.HYBRID,
            "welcome_message": "Bienvenue sur le Wi-Fi de la Ville de Dakar.",
        },
    },
    {
        "name": "Marché Kermel (démonstration)",
        "address": "Rue Salva, Dakar Plateau",
        "latitude": "14.671900",
        "longitude": "-17.432600",
        "zone": {
            "code": "demo-kermel",
            "label": "Marché Kermel",
            "access_mode": Zone.AccessMode.PAID,
            "welcome_message": "Accès Wi-Fi du marché Kermel.",
        },
    },
    {
        "name": "Bibliothèque municipale (démonstration)",
        "address": "Avenue Cheikh Anta Diop, Dakar",
        "latitude": "14.693500",
        "longitude": "-17.462900",
        "zone": {
            "code": "demo-bibliotheque",
            "label": "Bibliothèque municipale",
            "access_mode": Zone.AccessMode.FREE,
            "welcome_message": "Accès gratuit offert par la Ville de Dakar.",
        },
    },
]

GIGABYTE = 1_000_000_000

PLANS: list[dict[str, Any]] = [
    {
        "code": "gratuit",
        "name": "Accès gratuit",
        "description": "30 minutes offertes, débit réduit.",
        "type": Plan.Type.FREE,
        "priority": 10,
        "version": {
            "price_xof": 0,
            "connection_seconds": 1800,
            "quota_total_bytes": 300_000_000,
            "bandwidth_down_kbps": 2048,
            "bandwidth_up_kbps": 512,
            "radius_profile_ref": "dakar-demo-gratuit",
        },
    },
    {
        "code": "heure-1",
        "name": "1 heure",
        "description": "Une heure de connexion, débit confortable.",
        "type": Plan.Type.PAID,
        "priority": 20,
        "version": {
            "price_xof": 500,
            "connection_seconds": 3600,
            "validity_seconds": 86400,
            "quota_total_bytes": GIGABYTE,
            "bandwidth_down_kbps": 8192,
            "bandwidth_up_kbps": 2048,
            "radius_profile_ref": "dakar-demo-1h",
        },
    },
    {
        "code": "journee",
        "name": "Journée",
        "description": "Accès pour 24 heures.",
        "type": Plan.Type.PAID,
        "priority": 30,
        "version": {
            "price_xof": 1500,
            "connection_seconds": 86400,
            "validity_seconds": 172800,
            "quota_total_bytes": 3 * GIGABYTE,
            "bandwidth_down_kbps": 8192,
            "bandwidth_up_kbps": 2048,
            "radius_profile_ref": "dakar-demo-jour",
        },
    },
    {
        "code": "semaine",
        "name": "Semaine",
        "description": "Sept jours d'accès, deux appareils simultanés.",
        "type": Plan.Type.PAID,
        "priority": 40,
        "version": {
            "price_xof": 5000,
            "connection_seconds": 604800,
            "validity_seconds": 864000,
            "quota_total_bytes": 10 * GIGABYTE,
            "bandwidth_down_kbps": 8192,
            "bandwidth_up_kbps": 2048,
            "max_simultaneous_sessions": 2,
            "radius_profile_ref": "dakar-demo-semaine",
        },
    },
]


class Command(BaseCommand):
    help = "Create reproducible demonstration data. Never runs in production."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if settings.ENVIRONMENT == "production":
            raise CommandError(
                "Refusing to seed demonstration data in production "
                "(cahier des charges §1 rule 18, §21)."
            )

        groups = self._create_roles()
        organization = self._create_network()
        self._create_catalogue(organization)

        # Internal accounts exist for local development only (§21). Their passwords
        # are generated per run and printed once — never stored in the repository.
        if settings.ENVIRONMENT != "local":
            self.stdout.write(
                f"Environment is '{settings.ENVIRONMENT}': no demonstration account created."
            )
            return

        self._create_local_accounts(groups)

    def _create_roles(self) -> dict[str, Group]:
        groups = {}
        created = 0
        for role in INTERNAL_ROLES:
            groups[role], was_created = Group.objects.get_or_create(name=role)
            created += int(was_created)
        self.stdout.write(
            self.style.SUCCESS(f"Roles: {len(INTERNAL_ROLES)} present ({created} created).")
        )
        return groups

    def _create_network(self) -> Organization:
        organization, _ = Organization.objects.get_or_create(
            name=ORGANIZATION_NAME,
            defaults={"type": Organization.Type.CITY, "status": Organization.Status.ACTIVE},
        )
        for index, spec in enumerate(SITES, start=1):
            site, _ = Site.objects.get_or_create(
                organization=organization,
                name=spec["name"],
                defaults={
                    "address": spec["address"],
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "status": Site.Status.ACTIVE,
                },
            )
            zone_spec = spec["zone"]
            zone, _ = Zone.objects.get_or_create(
                code=zone_spec["code"],
                defaults={
                    "site": site,
                    "label": zone_spec["label"],
                    "access_mode": zone_spec["access_mode"],
                    "welcome_message": zone_spec["welcome_message"],
                    "status": Zone.Status.ACTIVE,
                },
            )
            Hotspot.objects.get_or_create(
                nas_identifier=f"demo-nas-{index:03d}",
                defaults={
                    "zone": zone,
                    "label": f"Borne de démonstration {index}",
                    "provider": "mock",
                    "status": Hotspot.Status.ACTIVE,
                },
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Network: {len(SITES)} sites, {len(SITES)} zones, {len(SITES)} hotspots."
            )
        )
        return organization

    def _create_catalogue(self, organization: Organization) -> None:
        zones = list(Zone.objects.filter(site__organization=organization))
        for spec in PLANS:
            plan, created = Plan.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "type": spec["type"],
                    "priority": spec["priority"],
                    "status": Plan.Status.PUBLISHED,
                },
            )
            if created:
                # The free offer is available everywhere; paid offers only where
                # the zone actually sells something.
                eligible = (
                    zones
                    if spec["type"] == Plan.Type.FREE
                    else [z for z in zones if z.access_mode != Zone.AccessMode.FREE]
                )
                plan.zones.set(eligible)

            if plan.current_version is None:
                version = PlanVersion.objects.create(
                    plan=plan, version=1, effective_at=timezone.now(), **spec["version"]
                )
                plan.current_version = version
                plan.save(update_fields=["current_version"])
        self.stdout.write(self.style.SUCCESS(f"Catalogue: {len(PLANS)} offres publiées."))

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
