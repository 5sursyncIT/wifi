"""Which offers a given hotspot may show (cahier des charges §8.2, §8.3)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.catalog.models import Plan, PlanVersion
from apps.network.models import Zone
from apps.portal.services import resolve_portal_context


def _publish(code, zone, **overrides):
    plan = Plan.objects.create(
        code=code,
        name=code,
        type=Plan.Type.PAID,
        status=overrides.pop("status", Plan.Status.PUBLISHED),
        **overrides,
    )
    if zone is not None:
        plan.zones.add(zone)
    version = PlanVersion.objects.create(
        plan=plan, version=1, price_xof=500, effective_at=timezone.now()
    )
    plan.current_version = version
    plan.save(update_fields=["current_version"])
    return plan


@pytest.mark.django_db
def test_only_offers_attached_to_the_resolved_zone_are_returned(hotspot, zone, site):
    mine = _publish("offre-de-la-zone", zone)
    other_zone = Zone.objects.create(
        site=site,
        code="autre-zone",
        label="Autre zone",
        access_mode=Zone.AccessMode.PAID,
        status=Zone.Status.ACTIVE,
    )
    _publish("offre-ailleurs", other_zone)

    context = resolve_portal_context(nas_identifier=hotspot.nas_identifier)

    assert [plan.code for plan in context.plans] == [mine.code]


@pytest.mark.django_db
def test_unpublished_and_hidden_offers_are_not_returned(hotspot, zone):
    _publish("brouillon", zone, status=Plan.Status.DRAFT)
    _publish("invisible", zone, is_visible=False)

    context = resolve_portal_context(nas_identifier=hotspot.nas_identifier)

    assert context.plans == []


@pytest.mark.django_db
def test_offers_outside_their_sale_window_are_not_returned(hotspot, zone):
    now = timezone.now()
    _publish("vente-terminee", zone, sale_ends_at=now - timedelta(days=1))
    _publish("vente-a-venir", zone, sale_starts_at=now + timedelta(days=1))

    context = resolve_portal_context(nas_identifier=hotspot.nas_identifier)

    assert context.plans == []


@pytest.mark.django_db
def test_offers_are_ordered_by_priority(hotspot, zone):
    _publish("second", zone, priority=20)
    _publish("premier", zone, priority=10)

    context = resolve_portal_context(nas_identifier=hotspot.nas_identifier)

    assert [plan.code for plan in context.plans] == ["premier", "second"]


@pytest.mark.django_db
def test_known_hotspot_with_no_usable_offer_falls_back(hotspot):
    context = resolve_portal_context(nas_identifier=hotspot.nas_identifier)

    assert context.is_fallback
    assert context.fallback_reason == "no_offer_available"


@pytest.mark.django_db
def test_hotspot_in_an_inactive_zone_falls_back(hotspot, zone):
    _publish("offre", zone)
    zone.status = Zone.Status.SUSPENDED
    zone.save(update_fields=["status"])

    context = resolve_portal_context(nas_identifier=hotspot.nas_identifier)

    assert context.is_fallback
    assert context.fallback_reason == "zone_inactive"
    assert context.plans == []
