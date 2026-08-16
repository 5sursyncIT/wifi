"""Transactional outbox (cahier des charges §11.2).

The rule this exists to enforce: nothing fallible is called before the commit, and
nothing committed is lost when that call fails. A message is written in the same
transaction as the state that justifies it; the drain then calls the outside world.
"""

import logging
from collections.abc import Callable
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import OutboxMessage

logger = logging.getLogger(__name__)

Handler = Callable[[dict], None]
_HANDLERS: dict[str, Handler] = {}

MAX_BACKOFF_SECONDS = 3600


class PermanentHandlerError(Exception):
    """Retrying cannot help. The message goes to `failed`, in front of an operator."""


def register(topic: str) -> Callable[[Handler], Handler]:
    def decorator(handler: Handler) -> Handler:
        _HANDLERS[topic] = handler
        return handler

    return decorator


def enqueue(topic: str, payload: dict) -> OutboxMessage:
    # Refused early: a topic nobody handles would sit pending forever, and the caller
    # would believe the work was scheduled.
    if topic not in _HANDLERS:
        raise ValueError(f"Unknown outbox topic {topic!r}.")
    return OutboxMessage.objects.create(topic=topic, payload=payload)


def _backoff(attempts: int) -> timedelta:
    return timedelta(
        seconds=min(settings.OUTBOX_BACKOFF_BASE_SECONDS * 2 ** (attempts - 1), MAX_BACKOFF_SECONDS)
    )


def _claim(limit: int) -> list[OutboxMessage]:
    """Take ownership of a batch in a short transaction, before any slow call.

    `skip_locked` lets several workers draw from the queue at once without blocking
    each other and without two of them taking the same row. A `processing` row whose
    `updated_at` predates the claim timeout is reclaimed too: a worker can die between
    claiming a message and reporting its outcome, and such a claim is presumed dead.

    A row whose `attempts` already reached `OUTBOX_MAX_ATTEMPTS` is routed to `failed`
    here instead of being claimed again. `_reschedule` enforces the same cap, but only
    runs when the handler raises a catchable exception; a handler that kills the
    worker outright never reaches it, so a message that always crashes its worker
    would otherwise be reclaimed and re-attempted forever. Checking the cap at claim
    time closes that gap for every claimed row, reclaimed or not.
    """
    now = timezone.now()
    stale_before = now - timedelta(seconds=settings.OUTBOX_CLAIM_TIMEOUT_SECONDS)
    with transaction.atomic():
        candidates = list(
            OutboxMessage.objects.select_for_update(skip_locked=True)
            .filter(
                Q(status=OutboxMessage.Status.PENDING, available_at__lte=now)
                | Q(status=OutboxMessage.Status.PROCESSING, updated_at__lte=stale_before)
            )
            .order_by("available_at")[:limit]
        )
        claimed = []
        for message in candidates:
            if message.attempts >= settings.OUTBOX_MAX_ATTEMPTS:
                message.status = OutboxMessage.Status.FAILED
                message.last_error = "Attempts exhausted; the worker did not report an outcome."
                message.save(update_fields=["status", "last_error", "updated_at"])
                logger.error(
                    "Outbox %s exhausted its retries without reporting an outcome.",
                    message.topic,
                )
                continue
            message.status = OutboxMessage.Status.PROCESSING
            message.attempts += 1
            message.save(update_fields=["status", "attempts", "updated_at"])
            claimed.append(message)
    return claimed


def _reschedule(message: OutboxMessage, error: Exception) -> None:
    if message.attempts >= settings.OUTBOX_MAX_ATTEMPTS:
        message.status = OutboxMessage.Status.FAILED
        logger.error("Outbox %s exhausted its retries: %s", message.topic, error)
    else:
        message.status = OutboxMessage.Status.PENDING
        message.available_at = timezone.now() + _backoff(message.attempts)
    message.last_error = str(error)[:300]
    message.save(update_fields=["status", "available_at", "last_error", "updated_at"])


def drain(limit: int = 20) -> int:
    """Run every due message. Returns how many succeeded."""
    succeeded = 0
    for message in _claim(limit):
        handler = _HANDLERS.get(message.topic)
        if handler is None:
            message.status = OutboxMessage.Status.FAILED
            message.last_error = f"No handler registered for {message.topic!r}."
            message.save(update_fields=["status", "last_error", "updated_at"])
            continue

        try:
            handler(message.payload)
        except PermanentHandlerError as error:
            message.status = OutboxMessage.Status.FAILED
            message.last_error = str(error)[:300]
            message.save(update_fields=["status", "last_error", "updated_at"])
            logger.error("Outbox %s failed permanently: %s", message.topic, error)
        except Exception as error:  # any failure must delay, never lose the message
            _reschedule(message, error)
        else:
            message.status = OutboxMessage.Status.DONE
            message.last_error = ""
            message.save(update_fields=["status", "last_error", "updated_at"])
            succeeded += 1
    return succeeded
