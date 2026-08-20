"""CSV export of payments without personal identifiers (§8.13, §13.3)."""

from __future__ import annotations

import csv
import io
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.core.audit import record_audit

DAKAR = ZoneInfo("Africa/Dakar")
FIELDS = (
    "order_number",
    "paid_at",
    "amount_xof",
    "fees_xof",
    "provider",
    "status",
    "zone_code",
    "plan_code",
)


def payments_csv(queryset, *, actor) -> bytes:
    rows = list(
        queryset.select_related(
            "order",
            "order__zone",
            "order__plan_version",
            "order__plan_version__plan",
        )
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    for payment in rows:
        paid_at = payment.order.paid_at
        writer.writerow(
            {
                "order_number": payment.order.order_number,
                "paid_at": timezone.localtime(paid_at, DAKAR).isoformat() if paid_at else "",
                "amount_xof": payment.amount_xof,
                "fees_xof": payment.fees_xof,
                "provider": payment.provider,
                "status": payment.status,
                "zone_code": payment.order.zone.code,
                "plan_code": payment.order.plan_version.plan.code,
            }
        )
    if rows:
        record_audit(
            actor=actor,
            action="payment.export",
            target=rows[0],
            after={"count": len(rows)},
        )
    return buffer.getvalue().encode("utf-8")
