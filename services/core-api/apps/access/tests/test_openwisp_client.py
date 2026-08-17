"""HTTP adapter for OpenWISP (cahier des charges §11, DW-P5-02)."""

import httpx
import pytest
import respx
from django.test import override_settings

from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkPermanentError, NetworkTemporaryError
from apps.access.providers.openwisp import OpenWispClient

BASE = "http://openwisp.test"
ASSIGN = f"{BASE}/api/v1/dakar/radius/assign-group/"

OPENWISP = dict(
    NETWORK_PROVIDER="openwisp",
    OPENWISP_BASE_URL=BASE,
    OPENWISP_API_TOKEN="test-token",
    OPENWISP_ORGANIZATION_ID="org-1",
    OPENWISP_ORGANIZATION_SLUG="ville-de-dakar",
    OPENWISP_HTTP_TIMEOUT_SECONDS=10,
    OPENWISP_RETRY_MAX=2,
    OPENWISP_CIRCUIT_FAILURES=5,
    OPENWISP_CIRCUIT_OPEN_SECONDS=30,
)


@pytest.fixture(autouse=True)
def _reset():
    OpenWispClient.reset()
    yield
    OpenWispClient.reset()


@override_settings(**OPENWISP)
def test_the_factory_returns_the_openwisp_client():
    assert isinstance(get_network_provider(), OpenWispClient)


@override_settings(**OPENWISP)
@respx.mock
def test_assign_plan_posts_the_group_and_reports_applied():
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "citizen-1",
                "group_name": "dakar-1h",
                "organization": "org-1",
                "changed": True,
            },
        )
    )

    result = OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert result.applied is True
    assert result.profile_ref == "dakar-1h"
    assert respx.calls.last.request.headers["Authorization"] == "Bearer test-token"


@override_settings(**OPENWISP)
@respx.mock
def test_assigning_the_same_group_is_a_noop():
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "citizen-1",
                "group_name": "dakar-1h",
                "organization": "org-1",
                "changed": False,
            },
        )
    )

    result = OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert result.applied is False
    assert result.profile_ref == "dakar-1h"
    assert "already" in result.detail.lower()


@override_settings(**OPENWISP)
@respx.mock
def test_unknown_group_is_a_permanent_error():
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(400, json={"detail": "No RADIUS group."})
    )

    with pytest.raises(NetworkPermanentError):
        OpenWispClient().assign_plan("citizen-1", "missing-group")


@override_settings(**OPENWISP)
@respx.mock
def test_server_error_is_retryable():
    respx.post(ASSIGN).mock(return_value=httpx.Response(503))

    with pytest.raises(NetworkTemporaryError) as raised:
        OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert raised.value.retryable is True
