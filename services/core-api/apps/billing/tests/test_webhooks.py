"""Webhook reception: signature, idempotence, history and late confirmations (§8.5, §16.1)."""

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
from apps.billing.models import Order, Payment, WebhookEvent
from apps.billing.orders import expire, place_order
from apps.billing.providers.mock import MockPaymentProvider
from apps.core.models import OutboxMessage
from apps.core.outbox import drain

URL = "/api/v1/webhooks/payments/mock"


@pytest.fixture(autouse=True)
def reset_providers():
    MockPaymentProvider.reset()
    MockNetworkProvider.reset()
    yield
    MockPaymentProvider.reset()
    MockNetworkProvider.reset()


@pytest.fixture
def placed(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    return order


def post(client, body, headers):
    return client.post(URL, data=body, content_type="application/json", headers=headers)


def test_a_valid_webhook_pays_the_order_and_schedules_activation(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.entitlement.status == Entitlement.Status.PENDING_ACTIVATION
    assert OutboxMessage.objects.filter(topic="entitlement.activate").count() == 1


def test_the_scheduled_activation_makes_the_right_live(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed)
    post(client, body, headers)

    drain()

    placed.refresh_from_db()
    assert placed.entitlement.status == Entitlement.Status.ACTIVE


def test_a_webhook_arriving_before_the_browser_returns_is_honoured(client, placed):
    """§16.1 — nothing special is needed, and a test keeps it that way.

    The order is committed before the provider is ever called, so a confirmation that
    overtakes the browser still finds an order to match. The portal then simply polls
    an order that is already paid.
    """
    body, headers = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.entitlement is not None


def test_an_invalid_signature_is_recorded_and_changes_nothing(client, placed):
    body, _ = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, {"X-Signature": "forged"})

    assert response.status_code == 400
    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
    event = WebhookEvent.objects.get()
    assert event.outcome == WebhookEvent.Outcome.BAD_SIGNATURE
    assert event.signature_valid is False


def test_a_duplicate_webhook_never_activates_twice(client, placed):
    # §17 criterion 5.
    body, headers = MockPaymentProvider.build_webhook(placed)
    post(client, body, headers)

    response = post(client, body, headers)

    assert response.status_code == 200
    assert Entitlement.objects.count() == 1
    assert OutboxMessage.objects.filter(topic="entitlement.activate").count() == 1
    outcomes = set(WebhookEvent.objects.values_list("outcome", flat=True))
    assert outcomes == {WebhookEvent.Outcome.PROCESSED, WebhookEvent.Outcome.DUPLICATE}


def test_an_unrelated_integrity_error_is_not_acknowledged_as_a_duplicate(
    client, placed, monkeypatch
):
    body, headers = MockPaymentProvider.build_webhook(placed)

    def fail_enqueue(*args, **kwargs):
        raise IntegrityError("unrelated outbox integrity failure")

    monkeypatch.setattr("apps.billing.webhooks.enqueue", fail_enqueue)

    with pytest.raises(IntegrityError, match="unrelated outbox integrity failure"):
        post(client, body, headers)

    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
    assert not WebhookEvent.objects.exists()


def test_a_divergent_amount_is_refused(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed, amount_xof=1)

    response = post(client, body, headers)

    assert response.status_code == 400
    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
    assert WebhookEvent.objects.get().outcome == WebhookEvent.Outcome.AMOUNT_MISMATCH


def test_a_divergent_payee_is_refused(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed, payee="quelquun-dautre")

    response = post(client, body, headers)

    assert response.status_code == 400
    assert WebhookEvent.objects.get().outcome == WebhookEvent.Outcome.AMOUNT_MISMATCH


def test_an_unknown_order_is_recorded_without_a_link(client, citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    body, headers = MockPaymentProvider.build_webhook(order)
    order.delete()

    response = post(client, body, headers)

    assert response.status_code == 404
    event = WebhookEvent.objects.get()
    assert event.outcome == WebhookEvent.Outcome.UNKNOWN_ORDER
    assert event.order_id is None


def test_a_refusal_fails_the_order(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed, status="refused")

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.FAILED
    assert not Entitlement.objects.exists()


def test_a_duplicate_refusal_is_recorded_without_failing(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed, status="refused")
    post(client, body, headers)

    response = post(client, body, headers)

    assert response.status_code == 200
    outcomes = set(WebhookEvent.objects.values_list("outcome", flat=True))
    assert outcomes == {WebhookEvent.Outcome.PROCESSED, WebhookEvent.Outcome.DUPLICATE}


def test_a_refusal_and_its_history_commit_together(client, placed, monkeypatch):
    body, headers = MockPaymentProvider.build_webhook(placed, status="refused")

    def fail_record(*args, **kwargs):
        raise IntegrityError("history write failed")

    monkeypatch.setattr("apps.billing.webhooks._record", fail_record)

    with pytest.raises(IntegrityError, match="history write failed"):
        post(client, body, headers)

    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
    assert placed.payments.get().status == Payment.Status.INITIATED


def test_a_confirmation_after_expiry_reactivates_the_order(client, placed):
    # §8.5 and §16.1: the citizen paid, so the right is granted and the discrepancy
    # is flagged rather than the payment being dropped.
    expire(placed)
    body, headers = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.reactivated_after_expiry is True
    assert placed.entitlement is not None
    assert placed.payments.get().status == Payment.Status.SUCCEEDED


def test_a_payment_confirmed_while_the_network_is_down_recovers(client, placed):
    """§17 criterion 6 — the reason the whole outbox exists."""
    MockNetworkProvider.scenario = "temporary_error"
    body, headers = MockPaymentProvider.build_webhook(placed)

    post(client, body, headers)
    drain()

    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.entitlement.status == Entitlement.Status.PENDING_ACTIVATION
    message = OutboxMessage.objects.get(topic="entitlement.activate")
    assert message.status == OutboxMessage.Status.PENDING
    assert message.attempts == 1

    MockNetworkProvider.scenario = "success"
    OutboxMessage.objects.update(available_at=timezone.now())
    drain()

    placed.refresh_from_db()
    assert placed.entitlement.status == Entitlement.Status.ACTIVE
    assert OutboxMessage.objects.get().status == OutboxMessage.Status.DONE
