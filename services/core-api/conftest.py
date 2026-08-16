from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from apps.catalog.models import Plan, PlanVersion
from apps.citizens.models import Citizen
from apps.network.models import Hotspot, Organization, Site, Zone


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Ville de Dakar — Test")


@pytest.fixture
def site(organization):
    return Site.objects.create(
        organization=organization,
        name="Place de l'Indépendance",
        latitude="14.667000",
        longitude="-17.437000",
        status=Site.Status.ACTIVE,
    )


@pytest.fixture
def zone(site):
    return Zone.objects.create(
        site=site,
        code="independance-centre",
        label="Place de l'Indépendance — centre",
        access_mode=Zone.AccessMode.HYBRID,
        status=Zone.Status.ACTIVE,
    )


@pytest.fixture
def hotspot(zone):
    return Hotspot.objects.create(
        zone=zone,
        nas_identifier="dakar-nas-001",
        label="Borne centre 1",
        status=Hotspot.Status.ACTIVE,
    )


@pytest.fixture
def plan(zone):
    plan = Plan.objects.create(
        code="heure-1",
        name="1 heure",
        type=Plan.Type.PAID,
        status=Plan.Status.PUBLISHED,
    )
    plan.zones.add(zone)
    return plan


@pytest.fixture
def plan_version(plan):
    version = PlanVersion.objects.create(
        plan=plan,
        version=1,
        price_xof=500,
        connection_seconds=3600,
        quota_total_bytes=1_000_000_000,
        radius_profile_ref="dakar-1h",
        effective_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    plan.current_version = version
    plan.save(update_fields=["current_version"])
    return version


@pytest.fixture
def current_terms(db):
    """The versions a citizen must accept to open an account (§8.1)."""
    from apps.citizens.models import TermsVersion

    return [
        TermsVersion.objects.create(
            type=TermsVersion.Type.TERMS,
            version="1.0",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        TermsVersion.objects.create(
            type=TermsVersion.Type.PRIVACY,
            version="1.0",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def citizen(db):
    return Citizen.objects.create(
        phone_e164="+221771234567", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )


@pytest.fixture
def order(citizen, zone, plan_version):
    from apps.billing.models import Order

    return Order.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        amount_xof=plan_version.price_xof,
        currency="XOF",
        idempotency_key="key-1",
        expires_at=timezone.now() + timedelta(minutes=30),
    )
