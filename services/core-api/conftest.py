from datetime import UTC, datetime

import pytest

from apps.catalog.models import Plan, PlanVersion
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
