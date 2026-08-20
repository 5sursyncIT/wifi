"""Support tickets opened from the portal (cahier des charges §8.12, §10.1)."""

import pytest
from django.core.cache import cache

from apps.citizens.tokens import issue_tokens
from apps.core.models import AuditLog
from apps.support.models import SupportTicket

pytestmark = pytest.mark.django_db

URL = "/api/v1/support/tickets"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def auth(citizen):
    tokens = issue_tokens(citizen)
    return {"Authorization": f"Bearer {tokens.access}"}


def test_an_anonymous_caller_can_open_a_ticket(client, hotspot):
    response = client.post(
        URL,
        {
            "nas_id": hotspot.nas_identifier,
            "category": "connexion",
            "message": "Je n'arrive pas à me connecter.",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ticket_number"].startswith("DW-SUP-")
    assert body["category"] == "connexion"
    assert body["status"] == SupportTicket.Status.OPEN
    ticket = SupportTicket.objects.get()
    assert ticket.hotspot_id == hotspot.pk
    assert ticket.citizen_id is None
    assert "phone" not in str(body).lower()
    assert AuditLog.objects.filter(action="ticket.create", target_id=str(ticket.pk)).exists()


def test_an_authenticated_ticket_is_attached_to_the_citizen(client, auth, citizen, hotspot):
    response = client.post(
        URL,
        {
            "nas_id": hotspot.nas_identifier,
            "category": "otp",
            "message": "Je n'ai pas reçu le SMS.",
        },
        content_type="application/json",
        headers=auth,
    )

    assert response.status_code == 201
    ticket = SupportTicket.objects.get()
    assert ticket.citizen_id == citizen.pk


def test_an_unknown_category_is_refused(client):
    response = client.post(
        URL,
        {"category": "espionnage", "message": "Bonjour."},
        content_type="application/json",
    )

    assert response.status_code == 400


def test_an_unknown_hotspot_is_refused(client):
    response = client.post(
        URL,
        {
            "nas_id": "borne-inconnue",
            "category": "autre",
            "message": "Je n'arrive pas à me connecter.",
        },
        content_type="application/json",
    )

    assert response.status_code == 404
    assert response.json()["code"] == "unknown_hotspot"


def test_opening_too_many_tickets_answers_429(client, settings):
    settings.SUPPORT_TICKET_MAX_PER_WINDOW = 1
    payload = {"category": "autre", "message": "Premier message suffisamment long."}
    assert client.post(URL, payload, content_type="application/json").status_code == 201

    response = client.post(
        URL,
        {"category": "autre", "message": "Second message suffisamment long."},
        content_type="application/json",
    )

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert SupportTicket.objects.count() == 1
