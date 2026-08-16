"""The seven scenarios the mock must reproduce (cahier des charges §11.3).

Phases 3 and 4 are built entirely against this mock, so each failure mode has to be
reachable on demand — otherwise the retry, outbox and reconciliation logic would only
ever be exercised on the happy path.
"""

import pytest

from apps.access.providers import get_network_provider
from apps.access.providers.base import (
    NetworkPermanentError,
    NetworkTemporaryError,
    NetworkTimeout,
    QuotaExhausted,
    SessionAlreadyActive,
)
from apps.access.providers.mock import MockNetworkProvider


@pytest.fixture(autouse=True)
def reset_provider():
    MockNetworkProvider.reset()
    yield
    MockNetworkProvider.reset()


def test_the_configured_provider_is_the_mock_by_default():
    assert isinstance(get_network_provider(), MockNetworkProvider)


def test_success_assigns_the_profile_and_records_it():
    provider = MockNetworkProvider()

    result = provider.assign_plan("citoyen-1", "dakar-demo-1h")

    assert result.applied is True
    assert MockNetworkProvider.assignments["citoyen-1"] == "dakar-demo-1h"


def test_the_same_assignment_twice_is_idempotent():
    provider = MockNetworkProvider()

    first = provider.assign_plan("citoyen-1", "dakar-demo-1h")
    second = provider.assign_plan("citoyen-1", "dakar-demo-1h")

    assert first.applied and second.applied
    assert MockNetworkProvider.assignment_calls == 2
    assert MockNetworkProvider.assignments == {"citoyen-1": "dakar-demo-1h"}


def test_timeout_scenario_raises_a_timeout():
    MockNetworkProvider.scenario = "timeout"

    with pytest.raises(NetworkTimeout):
        MockNetworkProvider().assign_plan("citoyen-1", "dakar-demo-1h")


def test_temporary_error_scenario_is_retryable():
    MockNetworkProvider.scenario = "temporary_error"

    with pytest.raises(NetworkTemporaryError) as raised:
        MockNetworkProvider().assign_plan("citoyen-1", "dakar-demo-1h")

    assert raised.value.retryable is True


def test_permanent_refusal_scenario_is_not_retryable():
    MockNetworkProvider.scenario = "permanent_error"

    with pytest.raises(NetworkPermanentError) as raised:
        MockNetworkProvider().assign_plan("citoyen-1", "dakar-demo-1h")

    assert raised.value.retryable is False


def test_session_already_active_scenario():
    MockNetworkProvider.scenario = "session_already_active"

    with pytest.raises(SessionAlreadyActive):
        MockNetworkProvider().assign_plan("citoyen-1", "dakar-demo-1h")


def test_quota_exhausted_scenario():
    MockNetworkProvider.scenario = "quota_exhausted"

    with pytest.raises(QuotaExhausted):
        MockNetworkProvider().assign_plan("citoyen-1", "dakar-demo-1h")


def test_duplicate_accounting_scenario_is_counted_once():
    MockNetworkProvider.scenario = "duplicate_accounting"
    provider = MockNetworkProvider()

    provider.record_accounting("citoyen-1", unique_id="session-1", seconds=600, bytes_total=50)
    provider.record_accounting("citoyen-1", unique_id="session-1", seconds=600, bytes_total=50)

    usage = provider.read_usage("citoyen-1")
    assert usage.seconds_used == 600
    assert usage.bytes_used == 50


def test_disconnect_reports_one_result_per_open_session():
    provider = MockNetworkProvider()
    provider.record_accounting("citoyen-1", unique_id="s1", seconds=10, bytes_total=1)
    provider.record_accounting("citoyen-1", unique_id="s2", seconds=10, bytes_total=1)

    results = provider.disconnect("citoyen-1")

    assert {result.session_id for result in results} == {"s1", "s2"}
    assert all(result.acknowledged for result in results)


def test_healthcheck_follows_the_scenario():
    provider = MockNetworkProvider()
    assert provider.healthcheck() is True

    MockNetworkProvider.scenario = "temporary_error"
    assert provider.healthcheck() is False
