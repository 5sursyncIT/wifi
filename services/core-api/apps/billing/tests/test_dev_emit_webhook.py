"""The mock payment emitter exists for local development and E2E only."""

import pytest

URL = "/api/v1/dev/payments/emit"
UNKNOWN_ORDER = {"order_number": "DW-20990101-UNKNOWN", "status": "succeeded"}


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_the_payment_emitter_is_absent_outside_local_and_test(client, settings, environment):
    settings.ENVIRONMENT = environment

    # A public route capable of marking orders paid must not exist in real environments.
    assert client.post(URL, UNKNOWN_ORDER).status_code == 404


def test_the_payment_emitter_is_absent_when_a_real_provider_is_configured(client, settings):
    settings.PAYMENT_PROVIDER = "wave"

    assert client.post(URL, UNKNOWN_ORDER).status_code == 404


@pytest.mark.django_db
def test_the_payment_emitter_reaches_order_lookup_for_mock_tests(client):
    assert client.post(URL, UNKNOWN_ORDER).status_code == 404
