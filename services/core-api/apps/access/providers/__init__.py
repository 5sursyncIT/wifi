from django.conf import settings

from apps.access.providers.base import NetworkProvider
from apps.access.providers.mock import MockNetworkProvider

# The OpenWISP implementation arrives in phase 5, once the extension of ADR-0006 is
# hardened. Until then everything runs against the mock (§1 rule 7).
_PROVIDERS: dict[str, type[NetworkProvider]] = {"mock": MockNetworkProvider}


def get_network_provider() -> NetworkProvider:
    name = settings.NETWORK_PROVIDER
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise RuntimeError(
            f"Unknown NETWORK_PROVIDER {name!r}. Available: {', '.join(sorted(_PROVIDERS))}."
        ) from None


__all__ = ["MockNetworkProvider", "NetworkProvider", "get_network_provider"]
