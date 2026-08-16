"""The portal must never trust what the browser sends (cahier des charges §8.2)."""

import pytest

from apps.network.models import Zone
from apps.portal.services import UnknownHotspot, resolve_portal_context


@pytest.mark.django_db
def test_zone_is_resolved_from_the_nas_identifier(hotspot, zone):
    context = resolve_portal_context(nas_identifier=hotspot.nas_identifier)

    assert context.zone == zone
    assert context.hotspot == hotspot


@pytest.mark.django_db
def test_zone_claimed_by_the_browser_is_ignored(hotspot, zone, site):
    other = Zone.objects.create(
        site=site,
        code="zone-privee",
        label="Zone que le navigateur revendique",
        access_mode=Zone.AccessMode.FREE,
        status=Zone.Status.ACTIVE,
    )

    context = resolve_portal_context(
        nas_identifier=hotspot.nas_identifier, claimed_zone_code=other.code
    )

    assert context.zone == zone


@pytest.mark.django_db
def test_unknown_nas_identifier_is_refused(db):
    with pytest.raises(UnknownHotspot):
        resolve_portal_context(nas_identifier="borne-inconnue")
