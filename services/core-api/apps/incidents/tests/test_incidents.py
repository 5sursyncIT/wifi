"""Network incidents (cahier des charges §8.10)."""

import pytest
from django.contrib.auth import get_user_model

from apps.incidents.lifecycle import (
    acknowledge,
    close,
    open_incident,
    resolve,
    sync_hotspot_incidents,
)
from apps.incidents.models import Incident
from apps.network.models import Hotspot

pytestmark = pytest.mark.django_db

URL = "/api/v1/public/hotspots"


def test_marking_a_hotspot_down_opens_an_incident(hotspot):
    hotspot.status = Hotspot.Status.DOWN
    hotspot.save()

    incident = Incident.objects.get()
    assert incident.hotspot_id == hotspot.pk
    assert incident.priority == Incident.Priority.P2
    assert incident.alert_type == Incident.AlertType.EQUIPMENT_OFFLINE
    assert incident.source == Incident.Source.AUTOMATIC
    assert incident.status == Incident.Status.OPEN


def test_saving_a_down_hotspot_twice_does_not_open_a_second_incident(hotspot):
    hotspot.status = Hotspot.Status.DOWN
    hotspot.save()
    hotspot.save()

    assert Incident.objects.count() == 1


def test_a_degraded_hotspot_opens_a_p3_incident(hotspot):
    hotspot.status = Hotspot.Status.DEGRADED
    hotspot.save()

    incident = Incident.objects.get()
    assert incident.priority == Incident.Priority.P3
    assert incident.alert_type == Incident.AlertType.DEGRADED


def test_acknowledging_records_the_delay(hotspot):
    incident = open_incident(
        hotspot,
        priority=Incident.Priority.P2,
        alert_type=Incident.AlertType.EQUIPMENT_OFFLINE,
        source=Incident.Source.MANUAL,
        title="Borne hors ligne",
    )
    actor = get_user_model().objects.create_user("exploitant", password="x")

    acknowledge(incident, actor=actor)

    incident.refresh_from_db()
    assert incident.status == Incident.Status.ACKNOWLEDGED
    assert incident.acknowledged_at is not None
    assert incident.assigned_to_id == actor.pk
    assert incident.seconds_to_acknowledge is not None
    assert incident.seconds_to_acknowledge >= 0


def test_resolving_an_incident_stamps_the_resolution_time(hotspot):
    incident = open_incident(
        hotspot,
        priority=Incident.Priority.P2,
        alert_type=Incident.AlertType.EQUIPMENT_OFFLINE,
        source=Incident.Source.MANUAL,
        title="Borne hors ligne",
    )
    actor = get_user_model().objects.create_user("exploitant", password="x")
    acknowledge(incident, actor=actor)
    resolve(incident, actor=actor)

    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED
    assert incident.resolved_at is not None
    assert incident.seconds_to_resolve is not None


def test_restoring_a_hotspot_does_not_auto_close_the_incident(hotspot):
    hotspot.status = Hotspot.Status.DOWN
    hotspot.save()
    hotspot.status = Hotspot.Status.ACTIVE
    hotspot.save()

    assert Incident.objects.get().status == Incident.Status.OPEN


def test_the_public_map_counts_open_incidents(client, hotspot):
    assert client.get(URL).json()["sites"][0]["open_incident_count"] == 0

    hotspot.status = Hotspot.Status.DOWN
    hotspot.save()

    body = client.get(URL).json()["sites"][0]
    assert body["open_incident_count"] == 1
    assert hotspot.nas_identifier not in client.get(URL).content.decode()


def test_sync_is_a_no_op_for_an_active_hotspot(hotspot):
    sync_hotspot_incidents(hotspot)

    assert Incident.objects.count() == 0


def test_close_is_terminal(hotspot):
    incident = open_incident(
        hotspot,
        priority=Incident.Priority.P4,
        alert_type=Incident.AlertType.OTHER,
        source=Incident.Source.MANUAL,
        title="Contrôle",
    )
    actor = get_user_model().objects.create_user("exploitant", password="x")
    close(incident, actor=actor)

    incident.refresh_from_db()
    assert incident.status == Incident.Status.CLOSED
    assert incident.resolved_at is not None
