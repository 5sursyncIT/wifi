import pytest
from django.core.cache import cache
from django.db import OperationalError, connection


@pytest.mark.django_db
def test_health_endpoint_reports_ok_when_dependencies_are_reachable(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["cache"] == "ok"


@pytest.mark.django_db
def test_health_endpoint_reports_unavailable_when_cache_is_unreachable(client, monkeypatch):
    def refuse_connection(*args, **kwargs):
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(cache, "set", refuse_connection)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["cache"] == "error"


@pytest.mark.django_db
def test_health_endpoint_reports_environment_and_version(client):
    response = client.get("/api/v1/health")

    body = response.json()
    assert body["environment"] == "test"
    assert body["version"]


def test_health_endpoint_reports_unavailable_when_database_is_unreachable(client, monkeypatch):
    def refuse_connection():
        raise OperationalError("connection refused")

    monkeypatch.setattr(connection, "cursor", refuse_connection)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "error"
