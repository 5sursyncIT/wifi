"""Crash window: assign succeeded, entitlement not yet ACTIVE, replay is a no-op."""

import httpx
import pytest
import respx
from django.test import override_settings
from django.utils import timezone

from apps.access.activation import activate_entitlement, entitlement_for_order
from apps.access.models import Entitlement
from apps.access.providers.openwisp import OpenWispClient
from apps.access.tests.test_openwisp_client import ASSIGN, OPENWISP, USERS
from apps.billing.models import Order


@pytest.fixture
def paid_order(order):
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    return order


@override_settings(**OPENWISP)
@respx.mock
def test_replaying_activation_after_a_crash_does_not_reassign(paid_order):
    OpenWispClient.reset()
    username = str(paid_order.citizen_id)
    group = paid_order.plan_version.radius_profile_ref
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())

    respx.get(USERS).mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": "u1", "username": username}]}
        )
    )
    assign = respx.post(ASSIGN)
    assign.side_effect = [
        httpx.Response(
            200,
            json={
                "username": username,
                "group_name": group,
                "organization": "org-1",
                "changed": True,
            },
        ),
        httpx.Response(
            200,
            json={
                "username": username,
                "group_name": group,
                "organization": "org-1",
                "changed": False,
            },
        ),
    ]

    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    entitlement.refresh_from_db()
    assert entitlement.status == Entitlement.Status.ACTIVE

    entitlement.status = Entitlement.Status.PENDING_ACTIVATION
    entitlement.save(update_fields=["status", "updated_at"])

    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    entitlement.refresh_from_db()

    assert entitlement.status == Entitlement.Status.ACTIVE
    assert assign.call_count == 2
