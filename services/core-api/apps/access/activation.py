"""Activating a right that was paid for (cahier des charges §8.5, §11.2).

Unlike the free allowance, this runs after the money is in: a failure here must never
refuse the citizen, only delay them. Every failure therefore propagates so the outbox
reschedules, and the right stays `pending_activation` rather than becoming a refusal.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkError
from apps.core.outbox import PermanentHandlerError, register

logger = logging.getLogger(__name__)

TOPIC = "entitlement.activate"


def entitlement_for_order(order, *, starts_at) -> Entitlement:
    """The right an order produces, created at most once.

    The OneToOne on `Entitlement.order` means a concurrent second call raises rather
    than granting twice; `get_or_create` turns that into the existing row.
    """
    version = order.plan_version
    duration = version.connection_seconds or version.validity_seconds
    entitlement, _ = Entitlement.objects.get_or_create(
        order=order,
        defaults={
            "citizen": order.citizen,
            "plan_version": version,
            "zone": order.zone,
            "source": Entitlement.Source.PURCHASE,
            "status": Entitlement.Status.PENDING_ACTIVATION,
            "starts_at": starts_at,
            "ends_at": starts_at + timedelta(seconds=duration) if duration else None,
        },
    )
    return entitlement


@register(TOPIC)
def activate_entitlement(payload: dict) -> None:
    entitlement = (
        Entitlement.objects.select_related("plan_version", "citizen")
        .filter(pk=payload["entitlement_id"])
        .first()
    )

    if entitlement is None:
        raise PermanentHandlerError(f"Unknown entitlement {payload['entitlement_id']!r}.")

    if entitlement.status == Entitlement.Status.ACTIVE:
        # Already applied. Replaying must not assign the plan a second time (§16.1).
        return

    provider = get_network_provider()
    subscriber_ref = str(entitlement.citizen_id)
    try:
        provider.ensure_user(subscriber_ref)
        provider.assign_plan(subscriber_ref, entitlement.plan_version.radius_profile_ref)
    except NetworkError as error:
        if error.retryable:
            # Left pending on purpose: the outbox will come back. Marking it failed
            # would turn a temporary outage into a lost purchase.
            logger.warning("Activation of %s deferred: %s", entitlement.pk, error)
            raise
        entitlement.status = Entitlement.Status.ACTIVATION_FAILED
        entitlement.activation_error = str(error)[:200]
        entitlement.save(update_fields=["status", "activation_error", "updated_at"])
        raise PermanentHandlerError(str(error)) from error

    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.radius_username = subscriber_ref
    entitlement.radius_synced_at = timezone.now()
    entitlement.activation_error = ""
    entitlement.save(
        update_fields=[
            "status",
            "radius_username",
            "radius_synced_at",
            "activation_error",
            "updated_at",
        ]
    )
