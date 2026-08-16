from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SmsResult:
    """What a provider reports back about one message."""

    provider_reference: str
    accepted: bool
    cost_xof: int = 0
    failure_reason: str = ""


class SmsProvider(ABC):
    """Contract every SMS connector implements.

    Kept narrow on purpose: the platform only ever needs to send a short message and
    know whether the operator accepted it. Delivery receipts arrive later, by webhook.
    """

    name: str

    @abstractmethod
    def send(self, recipient_e164: str, body: str) -> SmsResult:
        """Hand one message to the operator."""

    @abstractmethod
    def healthcheck(self) -> bool:
        """True when the connector believes it can send."""
