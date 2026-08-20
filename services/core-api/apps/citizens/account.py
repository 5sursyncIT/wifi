"""Export and deletion of a citizen account (cahier des charges §8.1).

Deletion is anonymisation, not a physical drop: orders and payments stay, because
they are financial records. The original phone number is freed so it can open a
new account.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.access.models import Entitlement, NetworkSession
from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkError
from apps.citizens.models import Citizen, CitizenDevice, OtpRequest
from apps.citizens.tokens import revoke_all
from apps.core.audit import record_audit, snapshot
from apps.messaging.models import SmsMessage

logger = logging.getLogger(__name__)


def export_account(citizen: Citizen) -> dict:
    """Personal data the citizen is entitled to read (§8.1, §13.3).

    RADIUS profile names, payment secrets and OTP hashes stay out: they are not
    the citizen's data, and putting them in an export would spread them.
    """
    consents = [
        {
            "type": consent.terms_version.type,
            "version": consent.terms_version.version,
            "accepted_at": consent.accepted_at,
            "source": consent.source,
        }
        for consent in citizen.consents.select_related("terms_version").order_by("-accepted_at")
    ]
    devices = [
        {
            "mac_hash": device.mac_hash,
            "label": device.label,
            "first_seen_at": device.first_seen_at,
            "last_seen_at": device.last_seen_at,
        }
        for device in citizen.devices.all()
    ]
    entitlements = [
        {
            "id": entitlement.pk,
            "source": entitlement.source,
            "status": entitlement.status,
            "zone": entitlement.zone.code,
            "plan": entitlement.plan_version.plan.code,
            "starts_at": entitlement.starts_at,
            "ends_at": entitlement.ends_at,
        }
        for entitlement in citizen.entitlements.select_related("zone", "plan_version__plan")
    ]
    orders = [
        {
            "order_number": order.order_number,
            "amount_xof": order.amount_xof,
            "currency": order.currency,
            "status": order.status,
            "created_at": order.created_at,
            "paid_at": order.paid_at,
        }
        for order in citizen.orders.all()
    ]
    tickets = []
    if hasattr(citizen, "support_tickets"):
        tickets = [
            {
                "ticket_number": ticket.ticket_number,
                "category": ticket.category,
                "status": ticket.status,
                "opened_at": ticket.opened_at,
            }
            for ticket in citizen.support_tickets.all()
        ]

    payload = {
        "exported_at": timezone.now(),
        "citizen": {
            "id": citizen.pk,
            "phone_e164": citizen.phone_e164,
            "email": citizen.email,
            "first_name": citizen.first_name,
            "last_name": citizen.last_name,
            "preferred_language": citizen.preferred_language,
            "status": citizen.status,
            "verified_at": citizen.verified_at,
        },
        "consents": consents,
        "devices": devices,
        "entitlements": entitlements,
        "orders": orders,
        "tickets": tickets,
    }
    record_audit(
        actor=None,
        action="citizen.export",
        target=citizen,
        after={"source": "self"},
    )
    return payload


def _placeholder_phone(citizen: Citizen) -> str:
    # +999 is not a country calling code, so this cannot collide with a real number.
    return f"+999{citizen.pk.int % 10**11:011d}"


def delete_account(citizen: Citizen) -> None:
    """Anonymise the account and revoke live access. Idempotent on a deleted row."""
    if citizen.status == Citizen.Status.DELETED:
        return

    original_phone = citizen.phone_e164
    before = snapshot(citizen)

    try:
        get_network_provider().disconnect(str(citizen.pk))
    except NetworkError as error:
        logger.warning("Disconnect before deleting %s failed: %s", citizen.pk, error)

    now = timezone.now()
    placeholder = _placeholder_phone(citizen)

    with transaction.atomic():
        Entitlement.objects.filter(citizen=citizen, status=Entitlement.Status.ACTIVE).update(
            status=Entitlement.Status.REVOKED
        )
        NetworkSession.objects.filter(citizen=citizen, stop_at__isnull=True).update(stop_at=now)
        CitizenDevice.objects.filter(citizen=citizen).delete()
        OtpRequest.objects.filter(phone_e164=original_phone).update(phone_e164=placeholder)
        SmsMessage.objects.filter(recipient_e164=original_phone).update(recipient_e164=placeholder)
        revoke_all(citizen)

        citizen.phone_e164 = placeholder
        citizen.email = ""
        citizen.first_name = ""
        citizen.last_name = ""
        citizen.radius_username = ""
        citizen.status = Citizen.Status.DELETED
        citizen.save(
            update_fields=[
                "phone_e164",
                "email",
                "first_name",
                "last_name",
                "radius_username",
                "status",
                "updated_at",
            ]
        )
        record_audit(
            actor=None,
            action="citizen.delete",
            target=citizen,
            before=before,
            after=snapshot(citizen),
        )
