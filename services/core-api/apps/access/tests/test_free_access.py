"""Free access allocation rules (cahier des charges §8.4, §11.2)."""

from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.access.free_access import FreeAccessRefused, grant_free_access
from apps.access.models import Entitlement, ZoneFreePolicy
from apps.access.providers.mock import MockNetworkProvider
from apps.catalog.models import Plan, PlanVersion
from apps.citizens.models import Citizen


@pytest.fixture(autouse=True)
def reset_provider():
    MockNetworkProvider.reset()
    yield
    MockNetworkProvider.reset()


@pytest.fixture
def citizen(db):
    return Citizen.objects.create(
        phone_e164="+221771234567", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )


@pytest.fixture
def free_plan(zone):
    plan = Plan.objects.create(
        code="gratuit", name="Accès gratuit", type=Plan.Type.FREE, status=Plan.Status.PUBLISHED
    )
    plan.zones.add(zone)
    version = PlanVersion.objects.create(
        plan=plan,
        version=1,
        price_xof=0,
        connection_seconds=1800,
        radius_profile_ref="dakar-demo-gratuit",
        effective_at=timezone.now(),
    )
    plan.current_version = version
    plan.save(update_fields=["current_version"])
    return plan


@pytest.fixture
def policy(zone):
    return ZoneFreePolicy.objects.create(zone=zone, daily_seconds=1800, cooldown_seconds=86400)


@pytest.mark.django_db
def test_an_eligible_citizen_receives_an_active_right(citizen, zone, free_plan, policy):
    entitlement = grant_free_access(citizen, zone)

    assert entitlement.status == Entitlement.Status.ACTIVE
    assert entitlement.source == Entitlement.Source.FREE
    assert entitlement.plan_version == free_plan.current_version


@pytest.mark.django_db
def test_the_radius_profile_is_actually_applied(citizen, zone, free_plan, policy):
    grant_free_access(citizen, zone)

    # The allowance must reach RADIUS, not just the database (§8.4).
    assert MockNetworkProvider.assignments[str(citizen.id)] == "dakar-demo-gratuit"


@pytest.mark.django_db
def test_a_second_grant_during_the_cooldown_is_refused(citizen, zone, free_plan, policy):
    grant_free_access(citizen, zone)

    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone)

    assert raised.value.reason == "cooldown"


@pytest.mark.django_db
def test_a_new_grant_is_allowed_once_the_cooldown_has_passed(citizen, zone, free_plan, policy):
    first = grant_free_access(citizen, zone)
    past = timezone.now() - timedelta(seconds=policy.cooldown_seconds + 60)
    Entitlement.objects.filter(pk=first.pk).update(created_at=past, starts_at=past)

    second = grant_free_access(citizen, zone)

    assert second.status == Entitlement.Status.ACTIVE


@pytest.mark.django_db
def test_a_zone_without_free_offer_is_refused(citizen, zone, policy):
    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone)

    assert raised.value.reason == "no_free_offer"


@pytest.mark.django_db
def test_a_zone_without_policy_is_refused(citizen, zone, free_plan):
    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone)

    assert raised.value.reason == "not_offered_here"


@pytest.mark.django_db
def test_a_disabled_policy_is_refused(citizen, zone, free_plan, policy):
    policy.is_enabled = False
    policy.save(update_fields=["is_enabled"])

    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone)

    assert raised.value.reason == "not_offered_here"


@pytest.mark.django_db
def test_outside_the_allowed_hours_it_is_refused(citizen, zone, free_plan, policy):
    # A window that cannot contain "now" whatever the clock says.
    now = timezone.localtime(timezone.now()).time()
    policy.usable_from = time(now.hour, 0)
    policy.usable_until = time(now.hour, 0)
    policy.save(update_fields=["usable_from", "usable_until"])

    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone)

    assert raised.value.reason == "outside_hours"


@pytest.mark.django_db
def test_a_blocked_citizen_is_refused(citizen, zone, free_plan, policy):
    citizen.status = Citizen.Status.BLOCKED
    citizen.save(update_fields=["status"])

    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone)

    assert raised.value.reason == "account_unusable"


@pytest.mark.django_db
def test_a_network_failure_leaves_the_right_inactive(citizen, zone, free_plan, policy):
    MockNetworkProvider.scenario = "temporary_error"

    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone)

    assert raised.value.reason == "activation_failed"
    # §11.2: a right is never announced as active before the network confirms it.
    entitlement = Entitlement.objects.get()
    assert entitlement.status == Entitlement.Status.ACTIVATION_FAILED
    assert entitlement.activation_error


@pytest.mark.django_db
def test_a_failed_activation_does_not_consume_the_cooldown(citizen, zone, free_plan, policy):
    MockNetworkProvider.scenario = "temporary_error"
    with pytest.raises(FreeAccessRefused):
        grant_free_access(citizen, zone)

    MockNetworkProvider.reset()

    # The citizen never got access, so they must not be locked out for a day.
    entitlement = grant_free_access(citizen, zone)
    assert entitlement.status == Entitlement.Status.ACTIVE


@pytest.mark.django_db
def test_a_third_device_is_refused_when_the_limit_is_two(citizen, zone, free_plan, policy):
    policy.cooldown_seconds = 0
    policy.max_devices = 2
    policy.save(update_fields=["cooldown_seconds", "max_devices"])

    grant_free_access(citizen, zone, device_hint="aa:aa:aa:aa:aa:01")
    grant_free_access(citizen, zone, device_hint="aa:aa:aa:aa:aa:02")

    with pytest.raises(FreeAccessRefused) as raised:
        grant_free_access(citizen, zone, device_hint="aa:aa:aa:aa:aa:03")

    assert raised.value.reason == "too_many_devices"


@pytest.mark.django_db
def test_the_same_device_can_reconnect_without_consuming_a_new_slot(
    citizen, zone, free_plan, policy
):
    policy.cooldown_seconds = 0
    policy.max_devices = 1
    policy.save(update_fields=["cooldown_seconds", "max_devices"])

    first = grant_free_access(citizen, zone, device_hint="aa:aa:aa:aa:aa:01")
    second = grant_free_access(citizen, zone, device_hint="AA:AA:AA:AA:AA:01")

    assert second.status == Entitlement.Status.ACTIVE
    assert first.citizen.devices.count() == 1
