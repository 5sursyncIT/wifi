"""Open-redirect protection for the captive portal (cahier des charges §8.2, §13.1)."""

import pytest

from apps.portal.services import safe_redirect_url

ALLOWED = ["portail.dakar.sn", "www.dakar.sn"]


@pytest.fixture(autouse=True)
def allowlist(settings):
    settings.PORTAL_ALLOWED_REDIRECT_HOSTS = ALLOWED


def test_url_on_an_allowed_host_is_kept():
    assert safe_redirect_url("https://portail.dakar.sn/statut") == "https://portail.dakar.sn/statut"


def test_url_on_another_host_is_refused():
    assert safe_redirect_url("https://collecte-de-donnees.example/vol") is None


def test_host_ending_with_an_allowed_host_is_refused():
    # The classic open-redirect bypass: "evil-dakar.sn" must not pass because
    # "dakar.sn" appears at the end of it.
    assert safe_redirect_url("https://evil-portail.dakar.sn.attaquant.example/") is None


def test_host_containing_an_allowed_host_is_refused():
    assert safe_redirect_url("https://portail.dakar.sn.attaquant.example/") is None


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//portail.dakar.sn/sans-schema",
        "",
        None,
    ],
)
def test_non_http_schemes_and_empty_values_are_refused(url):
    assert safe_redirect_url(url) is None
