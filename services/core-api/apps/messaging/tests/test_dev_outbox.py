"""The mock outbox endpoint exists for local development and E2E only."""

import pytest

from apps.messaging.providers.mock import MockSmsProvider

URL = "/api/v1/dev/sms-outbox"


@pytest.fixture(autouse=True)
def clear_outbox():
    MockSmsProvider.clear()
    yield
    MockSmsProvider.clear()


@pytest.mark.django_db
def test_the_outbox_is_readable_in_test(client):
    MockSmsProvider().send("+221771234567", "Dakar WiFi : votre code est 123456.")

    response = client.get(URL)

    assert response.status_code == 200
    assert response.json()["messages"][0]["body"].endswith("123456.")


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_the_outbox_is_absent_outside_local_and_test(client, settings, environment):
    settings.ENVIRONMENT = environment

    # Reading other people's verification codes must be impossible anywhere real,
    # whatever the SMS provider in use (§13.1).
    assert client.get(URL).status_code == 404


def test_the_outbox_is_absent_when_a_real_provider_is_configured(client, settings):
    settings.SMS_PROVIDER = "orange"

    assert client.get(URL).status_code == 404
