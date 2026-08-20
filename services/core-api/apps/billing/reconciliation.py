"""Compare local succeeded payments with the provider for a period (§8.13)."""

from django.db.models import Sum

from apps.billing.models import Payment, ReconciliationRun, Refund
from apps.billing.providers import get_payment_provider


def run_reconciliation(provider_name: str, period_start, period_end) -> ReconciliationRun:
    run = ReconciliationRun.objects.create(
        provider=provider_name,
        period_start=period_start,
        period_end=period_end,
        status=ReconciliationRun.Status.RUNNING,
    )
    provider = get_payment_provider()
    payments = Payment.objects.filter(
        provider=provider_name,
        status=Payment.Status.SUCCEEDED,
        order__paid_at__gte=period_start,
        order__paid_at__lte=period_end,
    )
    mismatches = []
    local_succeeded_xof = 0
    provider_succeeded_xof = 0
    for payment in payments:
        local_succeeded_xof += payment.amount_xof
        remote = provider.get_payment_status(payment.external_reference)
        provider_succeeded_xof += remote.amount_xof
        if remote.status != "succeeded" or remote.amount_xof != payment.amount_xof:
            mismatches.append(
                {
                    "payment_id": str(payment.pk),
                    "local": payment.amount_xof,
                    "remote": remote.amount_xof,
                    "remote_status": remote.status,
                }
            )

    refunded_xof = (
        Refund.objects.filter(
            status=Refund.Status.SUCCEEDED,
            processed_at__gte=period_start,
            processed_at__lte=period_end,
        ).aggregate(total=Sum("amount_xof"))["total"]
        or 0
    )
    run.totals_json = {
        "local_succeeded_xof": local_succeeded_xof,
        "provider_succeeded_xof": provider_succeeded_xof,
        "refunded_xof": refunded_xof,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    run.status = (
        ReconciliationRun.Status.MISMATCH if mismatches else ReconciliationRun.Status.BALANCED
    )
    run.save(update_fields=["totals_json", "status", "updated_at"])
    return run
