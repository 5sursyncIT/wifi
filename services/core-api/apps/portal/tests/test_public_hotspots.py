"""Public map of access points (cahier des charges §10.1, §8.9)."""

import pytest

from apps.network.models import Site

URL = "/api/v1/public/hotspots"


@pytest.mark.django_db
def test_public_sites_with_coordinates_are_listed(client, hotspot, site):
    body = client.get(URL).json()

    assert [entry["name"] for entry in body["sites"]] == [site.name]
    assert body["sites"][0]["hotspot_count"] == 1


@pytest.mark.django_db
def test_sites_hidden_from_the_public_are_not_listed(client, site):
    site.is_public = False
    site.save(update_fields=["is_public"])

    assert client.get(URL).json()["sites"] == []


@pytest.mark.django_db
def test_sites_without_coordinates_are_not_listed(client, organization):
    Site.objects.create(
        organization=organization, name="Site sans coordonnées", status=Site.Status.ACTIVE
    )

    assert client.get(URL).json()["sites"] == []


@pytest.mark.django_db
def test_network_identifiers_are_never_exposed(client, hotspot):
    # A public map must not hand out the identifiers the portal trusts (§8.2, §8.9).
    assert hotspot.nas_identifier not in client.get(URL).content.decode()
