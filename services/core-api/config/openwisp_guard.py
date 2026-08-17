from django.core.exceptions import ImproperlyConfigured

INSECURE_OPENWISP_URL_MARK = "example.invalid"
INSECURE_OPENWISP_TOKENS = frozenset({"", "change-me"})


def assert_openwisp_ready(network_provider: str, base_url: str, token: str) -> None:
    if network_provider != "openwisp":
        return
    if INSECURE_OPENWISP_URL_MARK in base_url or token in INSECURE_OPENWISP_TOKENS:
        raise ImproperlyConfigured(
            "OPENWISP_BASE_URL and OPENWISP_API_TOKEN must be set in production."
        )
