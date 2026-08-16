from django.conf import settings

from apps.messaging.providers.base import SmsProvider, SmsResult
from apps.messaging.providers.mock import MockSmsProvider

# Real connectors arrive in phase 7, one at a time and behind a feature flag (§18).
_PROVIDERS: dict[str, type[SmsProvider]] = {"mock": MockSmsProvider}


def get_sms_provider() -> SmsProvider:
    name = settings.SMS_PROVIDER
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise RuntimeError(
            f"Unknown SMS_PROVIDER {name!r}. Available: {', '.join(sorted(_PROVIDERS))}."
        ) from None


__all__ = ["MockSmsProvider", "SmsProvider", "SmsResult", "get_sms_provider"]
