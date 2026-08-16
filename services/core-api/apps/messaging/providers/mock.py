import logging
import uuid

from django.conf import settings

from apps.messaging.providers.base import SmsProvider, SmsResult

logger = logging.getLogger(__name__)


class MockSmsProvider(SmsProvider):
    """Local and test connector. Sends nothing.

    Keeps the last messages in memory so a test can assert on what was sent without
    reaching a network, and prints the body in local development only — that body
    carries the OTP code, which must never reach a log anywhere else (§13.1).
    """

    name = "mock"

    # Class-level on purpose: the provider is instantiated per call, the record is
    # what a test or a developer inspects afterwards.
    outbox: list[dict[str, str]] = []

    def send(self, recipient_e164: str, body: str) -> SmsResult:
        reference = f"mock-{uuid.uuid4()}"
        type(self).outbox.append({"to": recipient_e164, "body": body, "reference": reference})

        if settings.ENVIRONMENT == "local":
            logger.info("SMS mock → %s : %s", recipient_e164, body)

        return SmsResult(provider_reference=reference, accepted=True, cost_xof=0)

    def healthcheck(self) -> bool:
        return True

    @classmethod
    def clear(cls) -> None:
        cls.outbox.clear()
