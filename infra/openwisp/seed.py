"""Idempotent seed data for the disposable Dakar OpenWISP lab."""

from django.contrib.auth import get_user_model
from django.db import transaction
from openwisp_radius.utils import load_model
from openwisp_users.models import Organization, OrganizationUser
from rest_framework.authtoken.models import Token

User = get_user_model()
Nas = load_model("Nas")
OrganizationRadiusSettings = load_model("OrganizationRadiusSettings")
RadiusGroup = load_model("RadiusGroup")

GROUP_NAMES = (
    "dakar-demo-gratuit",
    "dakar-1h",
    "dakar-demo-1h",
    "dakar-demo-jour",
    "dakar-demo-semaine",
)


@transaction.atomic
def seed():
    organization, _ = Organization.objects.update_or_create(
        slug="ville-de-dakar",
        defaults={"name": "Ville de Dakar"},
    )
    OrganizationRadiusSettings.objects.update_or_create(
        organization=organization,
        defaults={"coa_enabled": True},
    )

    for name in GROUP_NAMES:
        RadiusGroup.objects.get_or_create(organization=organization, name=name)

    service_user, _ = User.objects.get_or_create(username="dakar-service")
    service_user.is_staff = True
    service_user.is_superuser = False
    service_user.set_unusable_password()
    service_user.save()
    OrganizationUser.objects.filter(user=service_user).exclude(
        organization=organization
    ).delete()
    OrganizationUser.objects.update_or_create(
        user=service_user,
        organization=organization,
        defaults={"is_admin": True},
    )
    token, _ = Token.objects.get_or_create(user=service_user)

    Nas.objects.update_or_create(
        organization=organization,
        name="0.0.0.0/0",
        defaults={"secret": "lab-nas-secret"},
    )

    print(f"OPENWISP_ORGANIZATION_ID={organization.pk}")
    print(f"OPENWISP_API_TOKEN={token.key}")


seed()
