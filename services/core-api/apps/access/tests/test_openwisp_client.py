"""HTTP adapter for OpenWISP (cahier des charges §11, DW-P5-02)."""

import json
import threading

import httpx
import pytest
import respx
from django.test import override_settings

from apps.access.providers import get_network_provider
from apps.access.providers.base import (
    DisconnectResult,
    NetworkPermanentError,
    NetworkTemporaryError,
    NetworkTimeout,
    Usage,
)
from apps.access.providers.openwisp import OpenWispClient

BASE = "http://openwisp.test"
ASSIGN = f"{BASE}/api/v1/dakar/radius/assign-group/"
USERS = f"{BASE}/api/v1/users/user/"
DISCONNECT = f"{BASE}/api/v1/dakar/radius/disconnect/"
USAGE = f"{BASE}/api/v1/radius/organization/ville-de-dakar/account/usage/"

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
    client = OpenWispClient()

    respx.post(ASSIGN).mock(return_value=httpx.Response(503))
    for _ in range(5):
        with pytest.raises(NetworkTemporaryError):
            client.assign_plan("citizen-1", "dakar-1h")

    opened_at = OpenWispClient._opened_at
    assert opened_at is not None
    monkeypatch.setattr(
        "apps.access.providers.openwisp.time.monotonic",
        lambda: opened_at + OPENWISP["OPENWISP_CIRCUIT_OPEN_SECONDS"],
    )

    calls_before = respx.calls.call_count
    barrier = threading.Barrier(2)
    outcomes: list[str | BaseException] = []

    def race_assign() -> None:
        try:
            barrier.wait(timeout=5)
            OpenWispClient().assign_plan("citizen-1", "dakar-1h")
            outcomes.append("ok")
        except NetworkTemporaryError as error:
            outcomes.append(error)

    threads = [threading.Thread(target=race_assign) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(outcomes) == 2
    gate_blocked = [
        outcome
        for outcome in outcomes
        if isinstance(outcome, NetworkTemporaryError)
        and "circuit is open" in str(outcome)
    ]
    assert len(gate_blocked) == 1
    assert respx.calls.call_count == calls_before + 3


@override_settings(**OPENWISP)
@respx.mock
def test_a_permanent_error_does_not_open_the_circuit():
    respx.post(ASSIGN).mock(return_value=httpx.Response(400, json={"detail": "no"}))
    client = OpenWispClient()

    for _ in range(6):
        with pytest.raises(NetworkPermanentError):
            client.assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == 6


@override_settings(**OPENWISP)
@respx.mock
def test_ensure_user_creates_when_missing():
    get_route = respx.get(USERS).mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    created = respx.post(USERS).mock(
        return_value=httpx.Response(201, json={"id": "u1", "username": "citizen-1"})
    )
    patch_route = respx.patch(f"{USERS}u1/").mock(
        return_value=httpx.Response(200, json={"id": "u1"})
    )

    assert OpenWispClient().ensure_user("citizen-1") == "citizen-1"

    assert get_route.calls.last.request.url.params["username"] == "citizen-1"
    post_body = json.loads(created.calls.last.request.content)
    assert post_body["username"] == "citizen-1"
    assert post_body["password"]
    assert post_body["email"] == "citizen-1@radius.dakar-wifi.invalid"
    patch_body = json.loads(patch_route.calls.last.request.content)
    assert patch_body == {"organization": "org-1"}


@override_settings(**OPENWISP)
@respx.mock
def test_ensure_user_is_idempotent_when_present():
    respx.get(USERS).mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": "u1", "username": "citizen-1"}]}
        )
    )
    post = respx.post(USERS)

    assert OpenWispClient().ensure_user("citizen-1") == "citizen-1"
    assert not post.called


@override_settings(**OPENWISP)
@respx.mock
def test_disconnect_returns_per_session_results_without_raising():
    respx.post(DISCONNECT).mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "citizen-1",
                "sessions": [
                    {"session": "abc", "nas": "10.0.0.1", "status": "acknowledged"},
                    {
                        "session": "def",
                        "nas": "10.0.0.2",
                        "status": "refused_or_unreachable",
                    },
                ],
            },
        )
    )

    results = OpenWispClient().disconnect("citizen-1")

    assert results == [
        DisconnectResult(session_id="abc", acknowledged=True, detail="acknowledged"),
        DisconnectResult(
            session_id="def", acknowledged=False, detail="refused_or_unreachable"
        ),
    ]


@override_settings(**OPENWISP)
@respx.mock
def test_read_usage_maps_daily_counters():
    usage_route = respx.get(USAGE).mock(
        return_value=httpx.Response(
            200,
            json={
                "checks": [
                    {
                        "attribute": "Max-Daily-Session",
                        "value": "10800",
                        "result": 600,
                        "type": "seconds",
                    },
                    {
                        "attribute": "Max-Daily-Session-Traffic",
                        "value": "3000000000",
                        "result": 50000000,
                        "type": "bytes",
                    },
                ]
            },
        )
    )

    usage = OpenWispClient().read_usage("citizen-1")

    assert usage_route.calls.last.request.url.params["username"] == "citizen-1"
    assert usage.seconds_used == 600
    assert usage.bytes_used == 50_000_000


@override_settings(**OPENWISP)
@respx.mock
def test_read_usage_defaults_counters_to_zero_when_checks_missing():
    respx.get(USAGE).mock(return_value=httpx.Response(200, json={"checks": []}))

    usage = OpenWispClient().read_usage("citizen-1")

    assert usage.seconds_used == 0
    assert usage.bytes_used == 0


@override_settings(**OPENWISP)
@respx.mock
def test_healthcheck_is_true_on_http_ok():
    respx.get(f"{USERS}").mock(return_value=httpx.Response(200, json={"results": []}))

    assert OpenWispClient().healthcheck() is True


@override_settings(**OPENWISP)
@respx.mock
def test_healthcheck_is_false_on_failure_and_does_not_open_the_circuit():
    respx.get(USERS).mock(return_value=httpx.Response(503))
    assert OpenWispClient().healthcheck() is False
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "x",
                "group_name": "dakar-1h",
                "organization": "org-1",
                "changed": True,
            },
        )
    )
    OpenWispClient().assign_plan("x", "dakar-1h")  # must still hit HTTP


@override_settings(**OPENWISP)
@respx.mock
def test_healthcheck_is_false_on_network_error_and_does_not_open_the_circuit():
    respx.get(USERS).mock(side_effect=httpx.TimeoutException("timed out"))
    assert OpenWispClient().healthcheck() is False
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "x",
                "group_name": "dakar-1h",
                "organization": "org-1",
                "changed": True,
            },
        )
    )
    OpenWispClient().assign_plan("x", "dakar-1h")  # must still hit HTTP
