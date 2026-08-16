"""Demonstration dataset for the network and catalogue (cahier des charges §21)."""

import pytest
from django.core.management import call_command

from apps.catalog.models import Plan
from apps.network.models import Hotspot, Organization, Site, Zone


@pytest.fixture
def seeded(db):
    call_command("seed_demo_data")


def test_seed_creates_the_demonstration_organization(seeded):
    organization = Organization.objects.get(name__startswith="Ville de Dakar")
    # Demonstration data must be recognisable at a glance so nobody mistakes it
    # for real municipal data.
    assert "Démonstration" in organization.name


def test_seed_creates_three_sites_and_one_zone_of_each_access_mode(seeded):
    assert Site.objects.count() == 3
    assert set(Zone.objects.values_list("access_mode", flat=True)) == {
        Zone.AccessMode.FREE,
        Zone.AccessMode.PAID,
        Zone.AccessMode.HYBRID,
    }


def test_seed_creates_one_hotspot_per_zone(seeded):
    assert Hotspot.objects.count() == Zone.objects.count()


def test_seed_creates_the_four_offers_with_a_current_version(seeded):
    plans = Plan.objects.all()
    assert {plan.code for plan in plans} == {"gratuit", "heure-1", "journee", "semaine"}
    assert all(plan.current_version is not None for plan in plans)


def test_free_offer_costs_nothing_and_paid_offers_are_priced_in_whole_xof(seeded):
    assert Plan.objects.get(code="gratuit").current_version.price_xof == 0
    for code in ("heure-1", "journee", "semaine"):
        price = Plan.objects.get(code=code).current_version.price_xof
        assert isinstance(price, int)
        assert price > 0


def test_seed_can_run_twice_without_duplicating(seeded):
    call_command("seed_demo_data")

    assert Organization.objects.count() == 1
    assert Site.objects.count() == 3
    assert Zone.objects.count() == 3
    assert Hotspot.objects.count() == 3
    assert Plan.objects.count() == 4
