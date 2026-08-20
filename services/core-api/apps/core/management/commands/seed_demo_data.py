from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.access.models import ZoneFreePolicy
from apps.catalog.models import Plan, PlanVersion
from apps.citizens.models import TermsVersion
from apps.network.models import Hotspot, Organization, Site, Zone
from apps.promotions.codes import import_codes
from apps.promotions.models import Campaign, Sponsor, VoucherBatch

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

# Least privilege for the Django admin until a dedicated back-office exists (§7).
# Each tuple is (app_label, model, action). superadmin is is_superuser and skipped.
ROLE_PERMISSIONS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "admin_ville": (
        ("network", "organization", "view"),
        ("network", "organization", "change"),
        ("network", "site", "view"),
        ("network", "site", "add"),
        ("network", "site", "change"),
        ("network", "zone", "view"),
        ("network", "zone", "add"),
        ("network", "zone", "change"),
        ("network", "hotspot", "view"),
        ("network", "hotspot", "add"),
        ("network", "hotspot", "change"),
        ("catalog", "plan", "view"),
        ("catalog", "plan", "add"),
        ("catalog", "plan", "change"),
        ("catalog", "planversion", "view"),
        ("access", "zonefreepolicy", "view"),
        ("access", "zonefreepolicy", "change"),
        ("citizens", "citizen", "view"),
        ("citizens", "citizen", "change"),
        ("billing", "order", "view"),
        ("billing", "refund", "view"),
        ("support", "supportticket", "view"),
        ("incidents", "incident", "view"),
        ("promotions", "sponsor", "view"),
        ("promotions", "sponsor", "add"),
        ("promotions", "sponsor", "change"),
        ("promotions", "campaign", "view"),
        ("promotions", "campaign", "add"),
        ("promotions", "campaign", "change"),
        ("promotions", "voucherbatch", "view"),
        ("promotions", "voucherbatch", "add"),
        ("promotions", "voucherbatch", "change"),
        ("promotions", "voucher", "view"),
        ("core", "auditlog", "view"),
    ),
    "exploitant_reseau": (
        ("network", "site", "view"),
        ("network", "site", "change"),
        ("network", "zone", "view"),
        ("network", "zone", "change"),
        ("network", "hotspot", "view"),
        ("network", "hotspot", "add"),
        ("network", "hotspot", "change"),
        ("access", "entitlement", "view"),
        ("access", "zonefreepolicy", "view"),
        ("access", "networksession", "view"),
        ("incidents", "incident", "view"),
        ("incidents", "incident", "add"),
        ("incidents", "incident", "change"),
        ("core", "auditlog", "view"),
    ),
    "responsable_commercial": (
        ("catalog", "plan", "view"),
        ("catalog", "plan", "add"),
        ("catalog", "plan", "change"),
        ("catalog", "planversion", "view"),
        ("catalog", "planversion", "add"),
        ("network", "zone", "view"),
        ("network", "site", "view"),
        ("promotions", "sponsor", "view"),
        ("promotions", "sponsor", "add"),
        ("promotions", "sponsor", "change"),
        ("promotions", "campaign", "view"),
        ("promotions", "campaign", "add"),
        ("promotions", "campaign", "change"),
        ("promotions", "voucherbatch", "view"),
        ("promotions", "voucherbatch", "add"),
        ("promotions", "voucherbatch", "change"),
        ("promotions", "voucher", "view"),
        ("core", "auditlog", "view"),
    ),
    "responsable_financier": (
        ("billing", "order", "view"),
        ("billing", "payment", "view"),
        ("billing", "webhookevent", "view"),
        ("billing", "refund", "view"),
        ("billing", "reconciliationrun", "view"),
        ("core", "auditlog", "view"),
    ),
    "agent_support": (
        ("citizens", "citizen", "view"),
        ("access", "entitlement", "view"),
        ("access", "networksession", "view"),
        ("billing", "order", "view"),
        ("network", "hotspot", "view"),
        ("network", "zone", "view"),
        ("support", "supportticket", "view"),
        ("support", "supportticket", "change"),
        ("incidents", "incident", "view"),
        ("core", "auditlog", "view"),
    ),
    "auditeur": (
        ("core", "auditlog", "view"),
        ("billing", "order", "view"),
        ("billing", "payment", "view"),
        ("billing", "webhookevent", "view"),
        ("billing", "refund", "view"),
        ("billing", "reconciliationrun", "view"),
        ("catalog", "plan", "view"),
        ("network", "site", "view"),
        ("network", "zone", "view"),
        ("promotions", "sponsor", "view"),
        ("promotions", "campaign", "view"),
        ("promotions", "voucherbatch", "view"),
        ("promotions", "voucher", "view"),
        ("support", "supportticket", "view"),
        ("incidents", "incident", "view"),
    ),
    "partenaire": (
        ("network", "site", "view"),
        ("network", "zone", "view"),
        ("promotions", "sponsor", "view"),
        ("promotions", "campaign", "view"),
        ("promotions", "voucherbatch", "view"),
        ("promotions", "voucher", "view"),
    ),
}

ORGANIZATION_NAME = "Ville de Dakar — Démonstration"
ORGANIZATION_I18N = {
    "en": {"name": "City of Dakar — Demonstration"},
    "wo": {"name": "Ville Dakar — Demo"},
}

# Coordinates are real Dakar landmarks so the map is readable; everything else is
# fictional and labelled as such.
SITES: list[dict[str, Any]] = [
    {
        "name": "Place de l'Indépendance (démonstration)",
        "i18n": {
            "en": {"name": "Independence Square (demonstration)"},
            "wo": {"name": "Place de l'Indépendance (demo)"},
        },
        "address": "Place de l'Indépendance, Dakar Plateau",
        "latitude": "14.667100",
        "longitude": "-17.437400",
        "zone": {
            "code": "demo-independance",
            "label": "Place de l'Indépendance",
            "access_mode": Zone.AccessMode.HYBRID,
            "welcome_message": "Bienvenue sur le Wi-Fi de la Ville de Dakar.",
            "i18n": {
                "en": {
                    "label": "Independence Square",
                    "welcome_message": "Welcome to the City of Dakar Wi-Fi.",
                },
                "wo": {
                    "label": "Place de l'Indépendance",
                    "welcome_message": "Dalal ak jàmm ci Wi-Fi bu Ville Dakar.",
                },
            },
        },
    },
    {
        "name": "Marché Kermel (démonstration)",
        "i18n": {
            "en": {"name": "Kermel Market (demonstration)"},
            "wo": {"name": "Marse Kermel (demo)"},
        },
        "address": "Rue Salva, Dakar Plateau",
        "latitude": "14.671900",
        "longitude": "-17.432600",
        "zone": {
            "code": "demo-kermel",
            "label": "Marché Kermel",
            "access_mode": Zone.AccessMode.PAID,
            "welcome_message": "Accès Wi-Fi du marché Kermel.",
            "i18n": {
                "en": {
                    "label": "Kermel Market",
                    "welcome_message": "Wi-Fi access at Kermel Market.",
                },
                "wo": {
                    "label": "Marse Kermel",
                    "welcome_message": "Wi-Fi bu marse Kermel.",
                },
            },
        },
    },
    {
        "name": "Bibliothèque municipale (démonstration)",
        "i18n": {
            "en": {"name": "Municipal library (demonstration)"},
            "wo": {"name": "Bibliyoteku dëkk (demo)"},
        },
        "address": "Avenue Cheikh Anta Diop, Dakar",
        "latitude": "14.693500",
        "longitude": "-17.462900",
        "zone": {
            "code": "demo-bibliotheque",
            "label": "Bibliothèque municipale",
            "access_mode": Zone.AccessMode.FREE,
            "welcome_message": "Accès gratuit offert par la Ville de Dakar.",
            "i18n": {
                "en": {
                    "label": "Municipal library",
                    "welcome_message": "Free access offered by the City of Dakar.",
                },
                "wo": {
                    "label": "Bibliyoteku dëkk",
                    "welcome_message": "Jàpp ci neen, Ville Dakar moo ko jox.",
                },
            },
        },
    },
]

GIGABYTE = 1_000_000_000

PLANS: list[dict[str, Any]] = [
    {
        "code": "gratuit",
        "name": "Accès gratuit",
        "description": "30 minutes offertes, débit réduit.",
        "i18n": {
            "en": {
                "name": "Free access",
                "description": "30 minutes included, reduced speed.",
            },
            "wo": {
                "name": "Jàpp ci neen",
                "description": "30 miniti ci neen, debit wu néew.",
            },
        },
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
        "code": "pass-dakar-1h",
        "name": "Pass Dakar 1 heure",
        "description": "Une heure de connexion sur la zone de démonstration.",
        "i18n": {
            "en": {
                "name": "Dakar 1-hour pass",
                "description": "One hour of connection on the demonstration zone.",
            },
            "wo": {
                "name": "Pass Dakar 1 waxtu",
                "description": "Waxtu wu nekk ci zone demo.",
            },
        },
        "type": Plan.Type.PAID,
        "priority": 15,
        "zone_code": "demo-independance",
        "version": {
            "price_xof": 500,
            "connection_seconds": 3600,
            "radius_profile_ref": "dakar-1h",
        },
    },
    {
        "code": "heure-1",
        "name": "1 heure",
        "description": "Une heure de connexion, débit confortable.",
        "i18n": {
            "en": {
                "name": "1 hour",
                "description": "One hour of connection, comfortable speed.",
            },
            "wo": {
                "name": "1 waxtu",
                "description": "Waxtu wu nekk, debit bu baax.",
            },
        },
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
        "i18n": {
            "en": {"name": "Day pass", "description": "24 hours of access."},
            "wo": {"name": "Bés", "description": "Jàpp bu 24 waxtu."},
        },
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
        "i18n": {
            "en": {
                "name": "Week pass",
                "description": "Seven days of access, two devices at once.",
            },
            "wo": {
                "name": "Ayubés",
                "description": "7 bés, ñaari apparayil.",
            },
        },
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
        self._create_terms()
        self._create_free_policies(organization)
        self._create_promotions(organization)

        # Internal accounts exist for local development only (§21). Their passwords
        # are generated per run and printed once — never stored in the repository.
        if settings.ENVIRONMENT != "local":
            self.stdout.write(
                f"Environment is '{settings.ENVIRONMENT}': no demonstration account created."
            )
            return

        self._create_local_accounts(groups)
        self._link_demo_partner()

    def _create_roles(self) -> dict[str, Group]:
        groups = {}
        created = 0
        for role in INTERNAL_ROLES:
            groups[role], was_created = Group.objects.get_or_create(name=role)
            created += int(was_created)
            self._assign_role_permissions(groups[role], role)
        self.stdout.write(
            self.style.SUCCESS(f"Roles: {len(INTERNAL_ROLES)} present ({created} created).")
        )
        return groups

    def _assign_role_permissions(self, group: Group, role: str) -> None:
        specs = ROLE_PERMISSIONS.get(role)
        if not specs:
            group.permissions.clear()
            return
        permissions = []
        for app_label, model, action in specs:
            codename = f"{action}_{model}"
            permissions.append(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    content_type__model=model,
                    codename=codename,
                )
            )
        group.permissions.set(permissions)

    def _create_network(self) -> Organization:
        organization, _ = Organization.objects.get_or_create(
            name=ORGANIZATION_NAME,
            defaults={"type": Organization.Type.CITY, "status": Organization.Status.ACTIVE},
        )
        organization.i18n = ORGANIZATION_I18N
        organization.save(update_fields=["i18n"])
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
            site.i18n = spec.get("i18n", {})
            site.save(update_fields=["i18n"])
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
            zone.i18n = zone_spec.get("i18n", {})
            zone.save(update_fields=["i18n"])
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
            plan.i18n = spec.get("i18n", {})
            plan.save(update_fields=["i18n"])
            if created:
                # The free offer is available everywhere; paid offers only where
                # the zone actually sells something.
                if "zone_code" not in spec:
                    eligible = (
                        zones
                        if spec["type"] == Plan.Type.FREE
                        else [z for z in zones if z.access_mode != Zone.AccessMode.FREE]
                    )
                    plan.zones.set(eligible)

            if zone_code := spec.get("zone_code"):
                zone = next(zone for zone in zones if zone.code == zone_code)
                plan.zones.add(zone)

            if plan.current_version is None:
                version = PlanVersion.objects.create(
                    plan=plan, version=1, effective_at=timezone.now(), **spec["version"]
                )
                plan.current_version = version
                plan.save(update_fields=["current_version"])
        self.stdout.write(self.style.SUCCESS(f"Catalogue: {len(PLANS)} offres publiées."))

    def _create_terms(self) -> None:
        """Placeholder documents. The real texts come from the City (§22 question 14)."""
        for document_type in (TermsVersion.Type.TERMS, TermsVersion.Type.PRIVACY):
            TermsVersion.objects.get_or_create(
                type=document_type,
                version="1.0-demo",
                defaults={
                    "summary": "Texte de démonstration, sans valeur juridique.",
                    "published_at": timezone.now(),
                },
            )
        self.stdout.write(self.style.SUCCESS("Conditions : 2 versions de démonstration."))

    def _create_free_policies(self, organization: Organization) -> None:
        """Free allowance on every zone that is not paid-only."""
        eligible = Zone.objects.filter(site__organization=organization).exclude(
            access_mode=Zone.AccessMode.PAID
        )
        for zone in eligible:
            ZoneFreePolicy.objects.get_or_create(
                zone=zone,
                defaults={
                    "daily_seconds": 1800,
                    "daily_bytes": 300_000_000,
                    "cooldown_seconds": 86400,
                    "max_devices": 2,
                },
            )
        self.stdout.write(
            self.style.SUCCESS(f"Accès gratuit : {eligible.count()} zone(s) configurée(s).")
        )

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

    def _create_promotions(self, organization: Organization) -> None:
        zone = Zone.objects.get(code="demo-independance")
        plan = Plan.objects.get(code="pass-dakar-1h")
        sponsor, _ = Sponsor.objects.get_or_create(
            name="Partenaire Démonstration",
            defaults={
                "status": Sponsor.Status.ACTIVE,
                "contact_data": {"email": "partenaire@demo.invalid"},
            },
        )
        campaign, created = Campaign.objects.get_or_create(
            sponsor=sponsor,
            name="Campagne de démonstration",
            defaults={
                "start_at": timezone.now() - timedelta(days=1),
                "end_at": timezone.now() + timedelta(days=365),
                "status": Campaign.Status.ACTIVE,
                "budget_xof": 100_000,
            },
        )
        if created:
            campaign.zones.add(zone)
        batch, _ = VoucherBatch.objects.get_or_create(
            campaign=campaign,
            plan_version=plan.current_version,
            defaults={
                "zone": zone,
                "quantity": 5,
                "max_uses": 1,
                "expires_at": timezone.now() + timedelta(days=365),
            },
        )
        codes = [f"DEMO-TEST-{index:04d}" for index in range(1, 6)]
        issued = import_codes(batch, codes)
        if issued:
            self.stdout.write(
                self.style.WARNING(
                    "Coupons de démonstration (mock, une seule impression) : "
                    + ", ".join(issued)
                )
            )
        self.stdout.write(self.style.SUCCESS("Promotions : 1 sponsor, 1 campagne, 5 coupons."))

    def _link_demo_partner(self) -> None:
        user_model = get_user_model()
        partner = user_model.objects.filter(username="demo_partenaire").first()
        sponsor = Sponsor.objects.filter(name="Partenaire Démonstration").first()
        if partner is None or sponsor is None:
            return
        if sponsor.partner_user_id != partner.pk:
            sponsor.partner_user = partner
            sponsor.save(update_fields=["partner_user", "updated_at"])
