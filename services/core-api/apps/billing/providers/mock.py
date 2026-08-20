"""In-memory payment provider covering the journeys of §16.1 and ADR-0004.

Every scenario is reachable by setting `MockPaymentProvider.scenario`, exactly as for
MockNetworkProvider. `build_webhook` produces a genuinely signed body so tests post it
to the real endpoint instead of calling the processing function directly — the signature
check is then exercised rather than bypassed.
"""

import hashlib
import hmac
import json

from django.conf import settings

from apps.billing.providers.base import (
    Mode,
    PaymentIntent,
    PaymentProvider,
    PaymentStatus,
    PaymentTemporaryError,
    RefundResult,
    WebhookPayload,
)

SCENARIOS = (
    "push_success",
    "push_refused",
    "push_timeout",
    "push_abandoned",
    "redirect_required",
    "provider_unavailable",
)

SIGNATURE_HEADER = "X-Signature"


class MockPaymentProvider(PaymentProvider):
    name = "mock"
    expected_payee = "dakar-wifi-mock"

    scenario: str = "push_success"
    statuses: dict[str, str] = {}
    amounts: dict[str, int] = {}
    refunded: dict[str, int] = {}

    @classmethod
    def reset(cls) -> None:
        cls.scenario = "push_success"
        cls.statuses = {}
        cls.amounts = {}
        cls.refunded = {}

    @staticmethod
    def reference_for(order) -> str:
        return f"MOCK-{order.order_number}"

    def create_payment(self, order) -> PaymentIntent:
        if type(self).scenario == "provider_unavailable":
            raise PaymentTemporaryError("Le prestataire est momentanément indisponible.")

        reference = self.reference_for(order)
        type(self).statuses[reference] = "pending"
        type(self).amounts[reference] = order.amount_xof

        if type(self).scenario == "redirect_required":
            return PaymentIntent(
                mode=Mode.REDIRECT,
                external_reference=reference,
                redirect_url=f"https://paiement.exemple.test/{reference}",
            )
        return PaymentIntent(
            mode=Mode.PUSH,
            external_reference=reference,
            instructions="Validez le paiement sur votre téléphone.",
        )

    def get_payment_status(self, external_reference: str) -> PaymentStatus:
        return PaymentStatus(
            external_reference=external_reference,
            status=type(self).statuses.get(external_reference, "pending"),
            amount_xof=type(self).amounts.get(external_reference, 0),
        )

    def verify_webhook(self, headers, body: bytes) -> bool:
        return hmac.compare_digest(headers.get(SIGNATURE_HEADER, ""), self.sign(body))

    def parse_webhook(self, body: bytes) -> WebhookPayload:
        data = json.loads(body)
        return WebhookPayload(
            external_event_id=data["event_id"],
            external_reference=data["reference"],
            status=data["status"],
            amount_xof=int(data["amount"]),
            currency=data["currency"],
            payee=data["payee"],
            fees_xof=int(data.get("fees", 0)),
        )

    def refund(self, payment, amount_xof: int) -> RefundResult:
        reference = payment.external_reference
        type(self).refunded[reference] = type(self).refunded.get(reference, 0) + amount_xof
        return RefundResult(
            external_reference=f"REF-{reference}",
            amount_xof=amount_xof,
            status="succeeded",
        )

    def healthcheck(self) -> bool:
        return type(self).scenario != "provider_unavailable"

    # --- Test seam -----------------------------------------------------------------

    @staticmethod
    def sign(body: bytes) -> str:
        return hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()

    @classmethod
    def build_webhook(
        cls,
        order,
        *,
        status: str = "succeeded",
        event_id: str | None = None,
        amount_xof: int | None = None,
        currency: str | None = None,
        payee: str | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        """A body and headers the provider would send, signed for real."""
        body = json.dumps(
            {
                "event_id": event_id or f"EVT-{order.order_number}-{status}",
                "reference": cls.reference_for(order),
                "status": status,
                "amount": order.amount_xof if amount_xof is None else amount_xof,
                "currency": order.currency if currency is None else currency,
                "payee": cls.expected_payee if payee is None else payee,
                "fees": 0,
            },
            separators=(",", ":"),
        ).encode()
        return body, {SIGNATURE_HEADER: cls.sign(body)}
