"""Refund a succeeded payment (cahier des charges §8.5, §8.13).

A refund does not revoke the access right: that is a separate operator action.
"""

from django.db.models import Sum
from django.utils import timezone

from apps.billing.models import Refund
from apps.billing.orders import mark_refunded
from apps.billing.providers import get_payment_provider
from apps.core.audit import record_audit, snapshot


class RefundRefused(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def refund_payment(payment, amount_xof: int, reason: str, actor) -> Refund:
    from apps.billing.models import Payment

    if payment.status != Payment.Status.SUCCEEDED:
        raise RefundRefused(
            "payment_not_succeeded",
            "Seul un paiement réussi peut être remboursé.",
        )
    if amount_xof <= 0:
        raise RefundRefused("invalid_amount", "Le montant doit être strictement positif.")

    already = (
        payment.refunds.filter(status=Refund.Status.SUCCEEDED).aggregate(total=Sum("amount_xof"))[
            "total"
        ]
        or 0
    )
    if already + amount_xof > payment.amount_xof:
        raise RefundRefused(
            "amount_exceeds_payment",
            "Le remboursement dépasse le montant encaissé.",
        )

    refund = Refund.objects.create(
        payment=payment,
        amount_xof=amount_xof,
        reason=reason,
        requested_by=actor,
        status=Refund.Status.REQUESTED,
    )
    result = get_payment_provider().refund(payment, amount_xof)
    refund.status = Refund.Status.SUCCEEDED
    refund.external_reference = result.external_reference
    refund.processed_at = timezone.now()
    refund.save(update_fields=["status", "external_reference", "processed_at", "updated_at"])

    remaining_after = already + amount_xof
    mark_refunded(payment.order, partial=remaining_after < payment.amount_xof)
    record_audit(
        actor=actor,
        action="payment.refund",
        target=refund,
        before={},
        after=snapshot(refund),
    )
    return refund
