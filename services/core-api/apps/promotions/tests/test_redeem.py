"""Redeeming a voucher grants a right through the outbox (§8.6, §16.1)."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
from apps.citizens.models import Citizen
from apps.core.models import OutboxMessage
from apps.promotions.codes import issue_batch
from apps.promotions.models import Campaign, Sponsor, Voucher, VoucherBatch
from apps.promotions.redeem import VoucherRefused, redeem_voucher


@pytest.fixture(autouse=True)
def reset_provider_and_cache():
    MockNetworkProvider.reset()
    cache.clear()
    yield
    MockNetworkProvider.reset()
    cache.clear()


@pytest.fixture
def issued(plan_version, zone):
    sponsor = Sponsor.objects.create(name="Sponsor", status=Sponsor.Status.ACTIVE)
    campaign = Campaign.objects.create(
        sponsor=sponsor,
        name="Campagne",
        start_at=timezone.now() - timedelta(days=1),
        end_at=timezone.now() + timedelta(days=30),
        status=Campaign.Status.ACTIVE,
    )
    campaign.zones.add(zone)
    batch = VoucherBatch.objects.create(
        plan_version=plan_version,
        campaign=campaign,
        zone=zone,
        quantity=2,
        max_uses=1,
        expires_at=timezone.now() + timedelta(days=7),
    )
    codes = issue_batch(batch)
    return {"batch": batch, "campaign": campaign, "codes": codes}


def test_a_valid_code_grants_a_voucher_right(citizen, zone, issued):
    entitlement = redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    assert entitlement.source == Entitlement.Source.VOUCHER
    assert entitlement.status == Entitlement.Status.ACTIVE
    assert MockNetworkProvider.assignments[str(citizen.id)] == "dakar-1h"
    voucher = Voucher.objects.get(pk=entitlement.voucher_id)
    assert voucher.uses_count == 1
    assert voucher.status == Voucher.Status.EXHAUSTED


def test_an_expired_code_is_refused(citizen, zone, issued):
    issued["batch"].expires_at = timezone.now() - timedelta(minutes=1)
    issued["batch"].save(update_fields=["expires_at"])

    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    assert raised.value.reason == "voucher_expired"
    assert Voucher.objects.filter(batch=issued["batch"], uses_count=0).count() == 2


def test_a_revoked_code_is_refused(citizen, zone, issued):
    from apps.promotions.codes import hash_code, revoke_voucher

    voucher = Voucher.objects.get(code_hash=hash_code(issued["codes"][0]))
    revoke_voucher(voucher)

    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    assert raised.value.reason == "voucher_revoked"


def test_an_unknown_code_is_refused(citizen, zone, issued):
    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(citizen, "ZZZZ-ZZZZ-ZZZZ", zone, "key-1")

    assert raised.value.reason == "voucher_not_found"


def test_a_consumed_code_cannot_be_used_again(citizen, zone, issued):
    redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    other = Citizen.objects.create(
        phone_e164="+221771111111", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )
    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(other, issued["codes"][0], zone, "key-2")

    assert raised.value.reason == "voucher_exhausted"
    assert Entitlement.objects.filter(source=Entitlement.Source.VOUCHER).count() == 1


def test_the_same_citizen_cannot_redeem_the_same_code_twice(citizen, zone, issued):
    redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(citizen, issued["codes"][0], zone, "key-2")

    assert raised.value.reason in {"voucher_exhausted", "voucher_already_used"}


def test_replaying_the_idempotency_key_returns_the_same_right(citizen, zone, issued):
    first = redeem_voucher(citizen, issued["codes"][0], zone, "key-1")
    second = redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    assert first.pk == second.pk
    assert Entitlement.objects.filter(source=Entitlement.Source.VOUCHER).count() == 1


def test_a_zone_mismatch_is_refused(citizen, issued, site):
    from apps.network.models import Zone

    other = Zone.objects.create(
        site=site,
        code="autre-zone",
        label="Ailleurs",
        access_mode=Zone.AccessMode.HYBRID,
        status=Zone.Status.ACTIVE,
    )

    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(citizen, issued["codes"][0], other, "key-1")

    assert raised.value.reason == "voucher_zone_mismatch"


def test_an_inactive_campaign_is_refused(citizen, zone, issued):
    issued["campaign"].status = Campaign.Status.ENDED
    issued["campaign"].save(update_fields=["status"])

    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    assert raised.value.reason == "voucher_campaign_inactive"


def test_a_network_outage_still_consumes_the_code(citizen, zone, issued):
    MockNetworkProvider.scenario = "temporary_error"

    entitlement = redeem_voucher(citizen, issued["codes"][0], zone, "key-1")

    entitlement.refresh_from_db()
    assert entitlement.status == Entitlement.Status.PENDING_ACTIVATION
    voucher = Voucher.objects.get(pk=entitlement.voucher_id)
    assert voucher.uses_count == 1
    assert OutboxMessage.objects.filter(topic="entitlement.activate").exists()


def test_the_eleventh_attempt_is_rate_limited(citizen, zone, issued, settings):
    settings.VOUCHER_MAX_ATTEMPTS_PER_CITIZEN = 10

    for index in range(10):
        with pytest.raises(VoucherRefused) as raised:
            redeem_voucher(citizen, "NOPE-NOPE-NOPE", zone, f"bad-{index}")
        assert raised.value.reason == "voucher_not_found"

    with pytest.raises(VoucherRefused) as raised:
        redeem_voucher(citizen, issued["codes"][0], zone, "key-ok")

    assert raised.value.reason == "rate_limited"
    assert Voucher.objects.filter(batch=issued["batch"], uses_count=0).count() == 2
