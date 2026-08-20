"""What the database itself guarantees about vouchers (§8.6, §9)."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.promotions.codes import hash_code, issue_batch, revoke_batch, revoke_voucher
from apps.promotions.models import Campaign, Sponsor, Voucher, VoucherBatch, VoucherRedemption


@pytest.fixture
def sponsor(db):
    return Sponsor.objects.create(name="Partenaire Test", status=Sponsor.Status.ACTIVE)


@pytest.fixture
def campaign(sponsor, zone):
    campaign = Campaign.objects.create(
        sponsor=sponsor,
        name="Campagne test",
        start_at=timezone.now() - timedelta(days=1),
        end_at=timezone.now() + timedelta(days=30),
        status=Campaign.Status.ACTIVE,
    )
    campaign.zones.add(zone)
    return campaign


@pytest.fixture
def batch(campaign, plan_version, zone):
    return VoucherBatch.objects.create(
        plan_version=plan_version,
        campaign=campaign,
        zone=zone,
        quantity=3,
        max_uses=1,
        expires_at=timezone.now() + timedelta(days=7),
    )


def test_issuing_a_batch_returns_plain_codes_and_stores_only_hashes(batch):
    codes = issue_batch(batch)

    assert len(codes) == 3
    assert len(set(codes)) == 3
    assert Voucher.objects.filter(batch=batch).count() == 3
    for code in codes:
        stored = Voucher.objects.get(code_hash=hash_code(code))
        assert code not in stored.code_hash
        assert stored.prefix == code.replace("-", "")[:4]
        assert stored.max_uses == 1
        assert stored.status == Voucher.Status.UNUSED


def test_a_batch_cannot_be_issued_twice(batch):
    issue_batch(batch)

    with pytest.raises(ValueError, match="already"):
        issue_batch(batch)


def test_code_hashes_are_unique(batch):
    issue_batch(batch)
    voucher = Voucher.objects.filter(batch=batch).first()

    with pytest.raises(IntegrityError), transaction.atomic():
        Voucher.objects.create(
            batch=batch,
            code_hash=voucher.code_hash,
            prefix="AAAA",
            max_uses=1,
        )


def test_revoking_a_voucher_blocks_it(batch):
    issue_batch(batch)
    voucher = Voucher.objects.filter(batch=batch).first()

    revoke_voucher(voucher)

    voucher.refresh_from_db()
    assert voucher.status == Voucher.Status.REVOKED


def test_revoking_a_batch_leaves_exhausted_codes_alone(batch):
    issue_batch(batch)
    unused, active, exhausted = list(Voucher.objects.filter(batch=batch).order_by("prefix"))
    unused.status = Voucher.Status.UNUSED
    unused.save(update_fields=["status"])
    active.status = Voucher.Status.ACTIVE
    active.uses_count = 1
    active.max_uses = 2
    active.save(update_fields=["status", "uses_count", "max_uses"])
    exhausted.status = Voucher.Status.EXHAUSTED
    exhausted.uses_count = 1
    exhausted.save(update_fields=["status", "uses_count"])

    revoke_batch(batch)

    unused.refresh_from_db()
    active.refresh_from_db()
    exhausted.refresh_from_db()
    assert unused.status == Voucher.Status.REVOKED
    assert active.status == Voucher.Status.REVOKED
    assert exhausted.status == Voucher.Status.EXHAUSTED


def test_a_citizen_may_redeem_a_code_only_once(batch, citizen, plan_version, zone):
    from apps.access.models import Entitlement

    issue_batch(batch)
    voucher = Voucher.objects.filter(batch=batch).first()
    entitlement = Entitlement.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        source=Entitlement.Source.VOUCHER,
        voucher=voucher,
        starts_at=timezone.now(),
    )
    VoucherRedemption.objects.create(
        voucher=voucher,
        citizen=citizen,
        entitlement=entitlement,
        idempotency_key="key-1",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        VoucherRedemption.objects.create(
            voucher=voucher,
            citizen=citizen,
            entitlement=Entitlement.objects.create(
                citizen=citizen,
                plan_version=plan_version,
                zone=zone,
                source=Entitlement.Source.VOUCHER,
                starts_at=timezone.now(),
            ),
            idempotency_key="key-2",
        )
