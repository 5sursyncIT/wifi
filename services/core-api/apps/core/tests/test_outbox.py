"""Transactional outbox: a failing outside world delays a message, never loses it (§11.2)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core import outbox
from apps.core.models import OutboxMessage

CALLS: list[dict] = []


@pytest.fixture(autouse=True)
def registry():
    CALLS.clear()

    @outbox.register("test.ok")
    def _ok(payload):
        CALLS.append(payload)

    @outbox.register("test.flaky")
    def _flaky(payload):
        CALLS.append(payload)
        raise RuntimeError("le contrôleur est indisponible")

    @outbox.register("test.permanent")
    def _permanent(payload):
        CALLS.append(payload)
        raise outbox.PermanentHandlerError("profil inconnu")

    yield
    for topic in ("test.ok", "test.flaky", "test.permanent"):
        outbox._HANDLERS.pop(topic, None)


def test_enqueue_writes_a_pending_message(db):
    message = outbox.enqueue("test.ok", {"id": "abc"})

    assert message.status == OutboxMessage.Status.PENDING
    assert message.attempts == 0


def test_enqueue_refuses_an_unregistered_topic(db):
    with pytest.raises(ValueError, match="Unknown outbox topic"):
        outbox.enqueue("test.nope", {})


def test_drain_runs_the_handler_and_marks_the_message_done(db):
    outbox.enqueue("test.ok", {"id": "abc"})

    assert outbox.drain() == 1
    assert CALLS == [{"id": "abc"}]
    assert OutboxMessage.objects.get().status == OutboxMessage.Status.DONE


def test_a_failure_reschedules_instead_of_losing_the_message(db):
    outbox.enqueue("test.flaky", {"id": "abc"})

    assert outbox.drain() == 0

    message = OutboxMessage.objects.get()
    assert message.status == OutboxMessage.Status.PENDING
    assert message.attempts == 1
    assert message.available_at > timezone.now()
    assert "indisponible" in message.last_error


def test_exhausting_the_attempts_surfaces_the_message_to_an_operator(db, settings):
    settings.OUTBOX_MAX_ATTEMPTS = 2
    outbox.enqueue("test.flaky", {"id": "abc"})

    for _ in range(2):
        OutboxMessage.objects.update(available_at=timezone.now())
        outbox.drain()

    message = OutboxMessage.objects.get()
    assert message.status == OutboxMessage.Status.FAILED
    assert message.attempts == 2


def test_a_permanent_error_does_not_retry(db):
    outbox.enqueue("test.permanent", {"id": "abc"})

    outbox.drain()

    message = OutboxMessage.objects.get()
    assert message.status == OutboxMessage.Status.FAILED
    assert message.attempts == 1


def test_a_message_scheduled_for_later_is_not_picked_up(db):
    outbox.enqueue("test.ok", {"id": "abc"})
    OutboxMessage.objects.update(available_at=timezone.now() + timedelta(minutes=5))

    assert outbox.drain() == 0
    assert CALLS == []
