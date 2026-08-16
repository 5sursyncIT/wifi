"""Scheduled work owned by the core app."""

from celery import shared_task

from apps.core.outbox import drain


@shared_task(name="core.drain_outbox")
def drain_outbox() -> int:
    return drain()
