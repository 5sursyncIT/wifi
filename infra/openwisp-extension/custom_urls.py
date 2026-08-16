"""Root URLconf: everything OpenWISP serves, plus our extension namespace.

Kept in a separate namespace (/api/v1/dakar/) so nothing can collide with upstream
routes when OpenWISP is upgraded.
"""

from django.urls import include, path
from openwisp.urls import urlpatterns as openwisp_urlpatterns

urlpatterns = openwisp_urlpatterns + [
    path(
        "api/v1/dakar/",
        include("openwisp.configuration.dakar_radius_ext.urls"),
    ),
]
