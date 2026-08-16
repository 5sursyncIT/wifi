from django.conf import settings

from apps.billing.providers.base import PaymentProvider
from apps.billing.providers.mock import MockPaymentProvider

# Wave, Orange Money and the card aggregator arrive in phase 7, each validated in
# sandbox before any commitment (ADR-0004). Until then everything runs on the mock.
_PROVIDERS: dict[str, type[PaymentProvider]] = {"mock": MockPaymentProvider}


def get_payment_provider() -> PaymentProvider:
    name = settings.PAYMENT_PROVIDER
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise RuntimeError(
            f"Unknown PAYMENT_PROVIDER {name!r}. Available: {', '.join(sorted(_PROVIDERS))}."
        ) from None


def is_known_provider(name: str) -> bool:
    """Whether a webhook path segment names a provider this platform speaks to."""
    return name in _PROVIDERS


__all__ = [
    "MockPaymentProvider",
    "PaymentProvider",
    "get_payment_provider",
    "is_known_provider",
]
