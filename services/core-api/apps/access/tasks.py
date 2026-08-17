"""Periodic repair of ACTIVE entitlements that drifted on the network."""

import logging

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkError

logger = logging.getLogger(__name__)


def reconcile_active_entitlements() -> int:
    if settings.NETWORK_PROVIDER != "openwisp":
        return 0
    provider = get_network_provider()
    now = timezone.now()
    rows = (
        Entitlement.objects.filter(status=Entitlement.Status.ACTIVE)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .order_by("pk")
    )
    repaired = 0
    for entitlement in rows.select_related("plan_version"):
        subscriber_ref = str(entitlement.citizen_id)
        try:
            provider.ensure_user(subscriber_ref)
            provider.assign_plan(subscriber_ref, entitlement.plan_version.radius_profile_ref)
        except NetworkError as error:
            logger.warning("Reconcile skipped %s: %s", entitlement.pk, error)
            continue
        repaired += 1
    return repaired


@shared_task(name="access.reconcile_active_entitlements")
def reconcile_active_entitlements_task() -> int:
    return reconcile_active_entitlements()
