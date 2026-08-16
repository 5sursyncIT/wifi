"""Contract between the platform and whatever moves the money (cahier des charges §8.5).

Isolating this keeps the domain free of any provider's specifics and lets Wave, Orange
Money or a card aggregator appear later without touching business code. Both journeys of
ADR-0004 are modelled from the start: push is nominal, redirect is the fallback.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass


class PaymentError(Exception):
    """Base for every payment-side failure."""

    retryable = False


class PaymentTimeout(PaymentError):
    """The provider did not answer in time."""

    retryable = True


class PaymentTemporaryError(PaymentError):
    """A transient failure. The caller should retry with backoff."""

    retryable = True


class PaymentPermanentError(PaymentError):
    """A refusal retrying cannot fix."""

    retryable = False


class PaymentRefused(PaymentError):
    """The payer declined or the provider rejected the payment."""

    retryable = False


class Mode:
    PUSH = "push"
    REDIRECT = "redirect"


@dataclass(frozen=True)
class PaymentIntent:
    mode: str
    external_reference: str
    redirect_url: str = ""
    instructions: str = ""


@dataclass(frozen=True)
class PaymentStatus:
    external_reference: str
    status: str
    amount_xof: int = 0
    fees_xof: int = 0


@dataclass(frozen=True)
class WebhookPayload:
    external_event_id: str
    external_reference: str
    status: str
    amount_xof: int
    currency: str
    payee: str
    fees_xof: int = 0


@dataclass(frozen=True)
class RefundResult:
    external_reference: str
    amount_xof: int
    status: str


class PaymentProvider(ABC):
    """Operations the platform needs from the payment layer."""

    name: str
    # The merchant account this platform expects to be credited. Compared strictly on
    # every webhook (§8.5); it belongs to the adapter, not to the order.
    expected_payee: str

    @abstractmethod
    def create_payment(self, order) -> PaymentIntent:
        """Ask the provider to start a payment for an order."""

    @abstractmethod
    def get_payment_status(self, external_reference: str) -> PaymentStatus:
        """Server-to-server truth, used by reconciliation."""

    @abstractmethod
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        """True when the signature proves the body came from the provider."""

    @abstractmethod
    def parse_webhook(self, body: bytes) -> WebhookPayload:
        """Normalise a provider body into the shared payload."""

    @abstractmethod
    def refund(self, payment, amount_xof: int) -> RefundResult:
        """Refund all or part of a payment."""

    @abstractmethod
    def healthcheck(self) -> bool:
        """True when the provider believes it is reachable."""
