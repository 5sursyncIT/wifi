"""Granting the free allowance of a zone (cahier des charges §8.4, §11.2).

Every rule is checked server-side, and the allowance is only announced as active once
the network layer has confirmed it. A right that says "active" while RADIUS knows
nothing about it is worse than a refusal: the citizen sees success and gets nothing.
"""

import hashlib
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.access.models import Entitlement, ZoneFreePolicy
from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkError
from apps.access.sessions import record_open_session
from apps.catalog.models import Plan
from apps.citizens.models import CitizenDevice

logger = logging.getLogger(__name__)


class FreeAccessRefused(Exception):
    """Free access cannot be granted. `reason` is a stable machine-readable code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _policy_for(zone):
    policy = ZoneFreePolicy.objects.filter(zone=zone).first()
    if policy is None or not policy.is_enabled:
        return None
    return policy


def _free_plan_for(zone):
    return (
        Plan.objects.filter(
            zones=zone,
            type=Plan.Type.FREE,
            status=Plan.Status.PUBLISHED,
            current_version__isnull=False,
        )
        .select_related("current_version")
        .order_by("priority")
        .first()
    )


def _within_hours(policy, moment) -> bool:
    if policy.usable_from is None or policy.usable_until is None:
        return True
    local_time = timezone.localtime(moment).time()
    if policy.usable_from == policy.usable_until:
        # An empty window is a closed window, not an open one.
        return False
    if policy.usable_from < policy.usable_until:
        return policy.usable_from <= local_time < policy.usable_until
    # Window crossing midnight.
    return local_time >= policy.usable_from or local_time < policy.usable_until


def _in_cooldown(citizen, zone, policy, moment) -> bool:
    if policy.cooldown_seconds <= 0:
        return False
    since = moment - timedelta(seconds=policy.cooldown_seconds)
    # Only rights that actually reached the citizen count: a failed activation must
    # not lock someone out of an allowance they never received.
    return Entitlement.objects.filter(
        citizen=citizen,
        zone=zone,
        source=Entitlement.Source.FREE,
        status__in=[
            Entitlement.Status.ACTIVE,
            Entitlement.Status.EXHAUSTED,
            Entitlement.Status.EXPIRED,
        ],
        starts_at__gte=since,
    ).exists()


def _hash_device_hint(device_hint: str) -> str:
    return hashlib.sha256(device_hint.strip().lower().encode()).hexdigest()


def _enforce_device_limit(citizen, policy, device_hint: str) -> None:
    """Refuse a new device once the zone's max_devices is reached (§8.4).

    Without a hint the gateway has not identified the client yet, so the check
    is skipped rather than locking every unknown MAC out of the allowance.
    """
    if not device_hint or policy.max_devices <= 0:
        return
    digest = _hash_device_hint(device_hint)
    existing = citizen.devices.filter(mac_hash=digest).first()
    if existing is not None:
        CitizenDevice.objects.filter(pk=existing.pk).update(last_seen_at=timezone.now())
        return
    if citizen.devices.count() >= policy.max_devices:
        raise FreeAccessRefused(
            "too_many_devices",
            "Le nombre maximal d'appareils pour l'accès gratuit est atteint.",
        )
    CitizenDevice.objects.create(citizen=citizen, mac_hash=digest)


def grant_free_access(citizen, zone, device_hint: str = "", *, hotspot=None) -> Entitlement:
    now = timezone.now()

    if not citizen.is_usable:
        raise FreeAccessRefused("account_unusable", "Ce compte ne peut pas être utilisé.")

    policy = _policy_for(zone)
    if policy is None:
        raise FreeAccessRefused(
            "not_offered_here", "L'accès gratuit n'est pas proposé sur ce point d'accès."
        )

    if not _within_hours(policy, now):
        raise FreeAccessRefused(
            "outside_hours", "L'accès gratuit n'est pas disponible à cette heure."
        )

    plan = _free_plan_for(zone)
    if plan is None:
        raise FreeAccessRefused("no_free_offer", "Aucune offre gratuite sur ce point d'accès.")

    if _in_cooldown(citizen, zone, policy, now):
        raise FreeAccessRefused("cooldown", "Vous avez déjà utilisé l'accès gratuit récemment.")

    _enforce_device_limit(citizen, policy, device_hint)

    version = plan.current_version
    duration = version.connection_seconds or policy.daily_seconds

    with transaction.atomic():
        entitlement = Entitlement.objects.create(
            citizen=citizen,
            plan_version=version,
            zone=zone,
            source=Entitlement.Source.FREE,
            status=Entitlement.Status.PENDING_ACTIVATION,
            starts_at=now,
            ends_at=now + timedelta(seconds=duration),
        )

    provider = get_network_provider()
    subscriber_ref = str(citizen.id)
    try:
        provider.ensure_user(subscriber_ref)
        provider.assign_plan(subscriber_ref, version.radius_profile_ref)
    except NetworkError as error:
        # Recorded rather than swallowed: the operator queue of §11.2 picks these up.
        Entitlement.objects.filter(pk=entitlement.pk).update(
            status=Entitlement.Status.ACTIVATION_FAILED, activation_error=str(error)[:200]
        )
        logger.warning("Free access activation failed for zone %s: %s", zone.code, error)
        raise FreeAccessRefused(
            "activation_failed", "L'activation a échoué. Réessayez dans un instant."
        ) from error

    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.radius_username = subscriber_ref
    entitlement.radius_synced_at = timezone.now()
    entitlement.save(update_fields=["status", "radius_username", "radius_synced_at"])
    record_open_session(entitlement=entitlement, hotspot=hotspot)
    return entitlement
