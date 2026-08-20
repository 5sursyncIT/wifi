"""Consume a voucher and grant the matching right (cahier des charges §8.6).

The code is spent in the same transaction as the entitlement and the outbox row,
so a network outage after commit delays activation rather than undoing the coupon.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.access.activation import TOPIC
from apps.access.models import Entitlement
from apps.core.audit import record_audit, snapshot
from apps.core.outbox import enqueue
from apps.core.tasks import drain_outbox
from apps.promotions.codes import hash_code
from apps.promotions.models import Voucher, VoucherRedemption

logger = logging.getLogger(__name__)


class VoucherRefused(Exception):
    """The code cannot be redeemed. `reason` is a stable machine-readable code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _attempts_key(citizen_id) -> str:
    return f"voucher:attempts:{citizen_id}"


def _raise_if_rate_limited(citizen) -> None:
    count = cache.get(_attempts_key(citizen.pk), 0)
    if count >= settings.VOUCHER_MAX_ATTEMPTS_PER_CITIZEN:
        raise VoucherRefused(
            "rate_limited",
            "Trop de tentatives. Patientez quelques minutes.",
        )


def _record_failure(citizen) -> None:
    key = _attempts_key(citizen.pk)
    cache.set(
        key,
        cache.get(key, 0) + 1,
        timeout=settings.VOUCHER_ATTEMPT_WINDOW_SECONDS,
    )


def _refuse(citizen, reason: str, message: str) -> None:
    _record_failure(citizen)
    raise VoucherRefused(reason, message)


def redeem_voucher(citizen, code: str, zone, idempotency_key: str) -> Entitlement:
    if not citizen.is_usable:
        raise VoucherRefused("account_unusable", "Ce compte ne peut pas être utilisé.")

    existing = (
        VoucherRedemption.objects.select_related("entitlement")
        .filter(citizen=citizen, idempotency_key=idempotency_key)
        .first()
    )
    if existing is not None:
        return existing.entitlement

    _raise_if_rate_limited(citizen)

    digest = hash_code(code)
    now = timezone.now()

    with transaction.atomic():
        voucher = (
            Voucher.objects.select_for_update(of=("self",))
            .select_related(
                "batch",
                "batch__campaign",
                "batch__plan_version",
                "batch__plan_version__plan",
            )
            .filter(code_hash=digest)
            .first()
        )
        if voucher is None:
            _refuse(citizen, "voucher_not_found", "Ce coupon n'est pas reconnu.")

        if voucher.status == Voucher.Status.REVOKED:
            _refuse(citizen, "voucher_revoked", "Ce coupon a été révoqué.")

        batch = voucher.batch
        if voucher.status == Voucher.Status.EXPIRED or batch.expires_at <= now:
            _refuse(citizen, "voucher_expired", "Ce coupon a expiré.")

        if (
            voucher.status == Voucher.Status.EXHAUSTED
            or voucher.uses_count >= voucher.max_uses
        ):
            _refuse(citizen, "voucher_exhausted", "Ce coupon a déjà été utilisé.")

        if VoucherRedemption.objects.filter(citizen=citizen, voucher=voucher).exists():
            _refuse(citizen, "voucher_already_used", "Vous avez déjà utilisé ce coupon.")

        campaign = batch.campaign
        if campaign is not None:
            if (
                campaign.status != campaign.Status.ACTIVE
                or now < campaign.start_at
                or now > campaign.end_at
            ):
                _refuse(
                    citizen,
                    "voucher_campaign_inactive",
                    "Cette campagne n'est plus active.",
                )
            if campaign.zones.exists() and not campaign.zones.filter(pk=zone.pk).exists():
                _refuse(
                    citizen,
                    "voucher_zone_mismatch",
                    "Ce coupon n'est pas valable sur ce point d'accès.",
                )

        if batch.zone_id and batch.zone_id != zone.pk:
            _refuse(
                citizen,
                "voucher_zone_mismatch",
                "Ce coupon n'est pas valable sur ce point d'accès.",
            )

        plan = batch.plan_version.plan
        if not plan.zones.filter(pk=zone.pk).exists():
            _refuse(
                citizen,
                "voucher_zone_mismatch",
                "Ce coupon n'est pas valable sur ce point d'accès.",
            )

        voucher.uses_count += 1
        voucher.status = (
            Voucher.Status.EXHAUSTED
            if voucher.uses_count >= voucher.max_uses
            else Voucher.Status.ACTIVE
        )
        voucher.save(update_fields=["uses_count", "status", "updated_at"])

        version = batch.plan_version
        duration = version.connection_seconds or version.validity_seconds
        entitlement = Entitlement.objects.create(
            citizen=citizen,
            plan_version=version,
            zone=zone,
            voucher=voucher,
            source=Entitlement.Source.VOUCHER,
            status=Entitlement.Status.PENDING_ACTIVATION,
            starts_at=now,
            ends_at=now + timedelta(seconds=duration) if duration else None,
        )
        VoucherRedemption.objects.create(
            voucher=voucher,
            citizen=citizen,
            entitlement=entitlement,
            idempotency_key=idempotency_key,
        )
        enqueue(TOPIC, {"entitlement_id": str(entitlement.pk)})
        record_audit(
            actor=None,
            action="voucher.redeem",
            target=voucher,
            before={},
            after=snapshot(voucher),
        )

    try:
        drain_outbox.delay()
    except Exception:
        logger.exception("Could not publish the immediate outbox drain task.")

    entitlement.refresh_from_db()
    return entitlement
