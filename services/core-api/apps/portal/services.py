"""Server-side resolution of the captive portal context (cahier des charges §8.2).

The browser sits between the gateway and this code, so nothing it sends about
identity, zone, price or destination is trusted. The only input that resolves a zone
is the network identifier presented by the hotspot itself.
"""

from dataclasses import dataclass, field
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import Plan
from apps.network.models import Hotspot, Zone


class UnknownHotspot(Exception):
    """Raised when no known hotspot matches the network identifier presented."""


@dataclass(frozen=True)
class PortalContext:
    hotspot: Hotspot
    zone: Zone
    plans: list = field(default_factory=list)
    fallback_reason: str = ""

    @property
    def is_fallback(self):
        """True when the hotspot is known but cannot currently sell anything.

        The portal then shows an explanatory screen instead of an empty catalogue,
        which is what §8.2 asks for a hotspot that is known but misconfigured.
        """
        return bool(self.fallback_reason)


def sellable_plans_for(zone):
    """Offers a client standing in `zone` may actually be shown right now."""
    now = timezone.now()
    return list(
        Plan.objects.filter(
            zones=zone,
            status=Plan.Status.PUBLISHED,
            is_visible=True,
            current_version__isnull=False,
        )
        .filter(Q(sale_starts_at__isnull=True) | Q(sale_starts_at__lte=now))
        .filter(Q(sale_ends_at__isnull=True) | Q(sale_ends_at__gte=now))
        .select_related("current_version")
        .order_by("priority", "name")
    )


def safe_redirect_url(url):
    """Return `url` when the portal may send a browser to it, otherwise None.

    The gateway hands the portal a "come back here afterwards" URL, and anyone on
    the network can rewrite it. Hosts are therefore compared by exact match against
    the allowlist: suffix matching would let `dakar.sn.attaquant.example` through.
    """
    if not url:
        return None

    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return None
    if not parts.hostname:
        return None
    if parts.hostname.lower() not in {
        host.lower() for host in settings.PORTAL_ALLOWED_REDIRECT_HOSTS
    }:
        return None

    return url


def resolve_portal_context(nas_identifier, claimed_zone_code=None):
    """Resolve the zone a client is connecting from.

    `claimed_zone_code` is accepted only so callers can pass the query string
    through untouched; it is deliberately never read. Trusting it would let anyone
    request the offers of a zone they are not standing in.
    """
    hotspot = (
        Hotspot.objects.select_related("zone", "zone__site", "zone__site__organization")
        .filter(nas_identifier=nas_identifier)
        .first()
    )
    if hotspot is None:
        raise UnknownHotspot(f"No hotspot registered for network identifier {nas_identifier!r}.")

    zone = hotspot.zone
    if zone.status != Zone.Status.ACTIVE:
        return PortalContext(hotspot=hotspot, zone=zone, fallback_reason="zone_inactive")

    plans = sellable_plans_for(zone)
    if not plans:
        return PortalContext(hotspot=hotspot, zone=zone, fallback_reason="no_offer_available")

    return PortalContext(hotspot=hotspot, zone=zone, plans=plans)
