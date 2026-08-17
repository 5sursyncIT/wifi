"""HTTP adapter for OpenWISP (cahier des charges §11, DW-P5-02)."""

import httpx
import pytest
import respx
from django.test import override_settings

from apps.access.providers import get_network_provider
from apps.access.providers.base import (
    NetworkPermanentError,
    NetworkTemporaryError,
    NetworkTimeout,
)
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


@override_settings(**OPENWISP)
@respx.mock
def test_a_transient_failure_is_retried_until_success(monkeypatch):
    monkeypatch.setattr("apps.access.providers.openwisp.time.sleep", lambda _s: None)
    route = respx.post(ASSIGN)
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(
            200,
            json={
                "username": "citizen-1",
                "group_name": "dakar-1h",
                "organization": "org-1",
                "changed": True,
            },
        ),
    ]

    result = OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert result.applied is True
    assert route.call_count == 3


@override_settings(**OPENWISP)
@respx.mock
def test_retries_stop_at_the_configured_cap(monkeypatch):
    monkeypatch.setattr("apps.access.providers.openwisp.time.sleep", lambda _s: None)
    respx.post(ASSIGN).mock(return_value=httpx.Response(503))

    with pytest.raises(NetworkTemporaryError):
        OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == 3  # 1 + OPENWISP_RETRY_MAX


@override_settings(**OPENWISP)
@respx.mock
def test_four_hundreds_are_not_retried():
    respx.post(ASSIGN).mock(return_value=httpx.Response(400, json={"detail": "no"}))

    with pytest.raises(NetworkPermanentError):
        OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == 1


@override_settings(**OPENWISP)
@respx.mock
def test_the_circuit_opens_after_consecutive_retryable_failures(monkeypatch):
    # _record_failure() runs once per exhausted assign_plan, not per HTTP attempt.
    monkeypatch.setattr("apps.access.providers.openwisp.time.sleep", lambda _s: None)
    respx.post(ASSIGN).mock(return_value=httpx.Response(503))
    client = OpenWispClient()

    for _ in range(5):
        with pytest.raises(NetworkTemporaryError):
            client.assign_plan("citizen-1", "dakar-1h")

    calls_before = respx.calls.call_count
    with pytest.raises(NetworkTemporaryError):
        client.assign_plan("citizen-1", "dakar-1h")
    assert respx.calls.call_count == calls_before  # no HTTP


@override_settings(**OPENWISP)
@respx.mock
def test_half_open_admits_only_one_probe(monkeypatch):
    monkeypatch.setattr("apps.access.providers.openwisp.time.sleep", lambda _s: None)
    client_a = OpenWispClient()
    client_b = OpenWispClient()

    respx.post(ASSIGN).mock(return_value=httpx.Response(503))
    for _ in range(5):
        with pytest.raises(NetworkTemporaryError):
            client_a.assign_plan("citizen-1", "dakar-1h")

    opened_at = OpenWispClient._opened_at
    assert opened_at is not None
    monkeypatch.setattr(
        "apps.access.providers.openwisp.time.monotonic",
        lambda: opened_at + OPENWISP["OPENWISP_CIRCUIT_OPEN_SECONDS"],
    )

    calls_before = respx.calls.call_count
    blocked_calls: list[int] = []

    def first_probe_request(request):
        blocked_calls.append(respx.calls.call_count)
        with pytest.raises(NetworkTemporaryError):
            client_b.assign_plan("citizen-1", "dakar-1h")
        blocked_calls.append(respx.calls.call_count)
        return httpx.Response(503)

    route = respx.post(ASSIGN)
    route.side_effect = [
        first_probe_request,
        httpx.Response(503),
        httpx.Response(503),
    ]

    with pytest.raises(NetworkTemporaryError):
        client_a.assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == calls_before + 3
    assert blocked_calls[0] == blocked_calls[1]


@override_settings(**OPENWISP)
@respx.mock
def test_a_permanent_error_does_not_open_the_circuit():
    respx.post(ASSIGN).mock(return_value=httpx.Response(400, json={"detail": "no"}))
    client = OpenWispClient()

    for _ in range(6):
        with pytest.raises(NetworkPermanentError):
            client.assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == 6
