"""Payment adapter contract and its mock (§8.5, ADR-0004, §16.1)."""

import pytest

from apps.billing.providers import get_payment_provider
from apps.billing.providers.base import (
    Mode,
    PaymentTemporaryError,
)
from apps.billing.providers.mock import MockPaymentProvider


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


def test_the_factory_returns_the_configured_provider():
    assert get_payment_provider().name == "mock"


def test_an_unknown_provider_is_refused(settings):
    settings.PAYMENT_PROVIDER = "nope"

    with pytest.raises(RuntimeError, match="Unknown PAYMENT_PROVIDER"):
        get_payment_provider()


def test_push_is_the_nominal_journey(order):
    intent = get_payment_provider().create_payment(order)

    assert intent.mode == Mode.PUSH
    assert intent.external_reference
    assert intent.instructions
    assert intent.redirect_url == ""


def test_the_redirect_fallback_carries_a_url(order):
    MockPaymentProvider.scenario = "redirect_required"

    intent = get_payment_provider().create_payment(order)

    assert intent.mode == Mode.REDIRECT
    assert intent.redirect_url.startswith("https://")


def test_an_unavailable_provider_raises_a_retryable_error(order):
    MockPaymentProvider.scenario = "provider_unavailable"

    with pytest.raises(PaymentTemporaryError) as raised:
        get_payment_provider().create_payment(order)

    assert raised.value.retryable is True


def test_a_signed_webhook_verifies_and_a_tampered_one_does_not(order):
    provider = get_payment_provider()
    body, headers = MockPaymentProvider.build_webhook(order)

    assert provider.verify_webhook(headers, body) is True
    assert provider.verify_webhook(headers, body + b" ") is False
    assert provider.verify_webhook({"X-Signature": "nope"}, body) is False


def test_a_webhook_parses_into_the_shared_payload(order):
    body, _ = MockPaymentProvider.build_webhook(order)

    payload = get_payment_provider().parse_webhook(body)

    assert payload.external_reference == f"MOCK-{order.order_number}"
    assert payload.status == "succeeded"
    assert payload.amount_xof == order.amount_xof
    assert payload.currency == order.currency
    assert payload.payee == MockPaymentProvider.expected_payee


def test_refund_returns_a_succeeded_result(order):
    payment = type("P", (), {"external_reference": "MOCK-1"})()
    result = get_payment_provider().refund(payment, 500)

    assert result.status == "succeeded"
    assert result.amount_xof == 500
    assert result.external_reference.startswith("REF-")
