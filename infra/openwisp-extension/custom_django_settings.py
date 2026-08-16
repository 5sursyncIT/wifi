"""Registers the Dakar WiFi RADIUS extension in the OpenWISP deployment.

OpenWISP imports this file at the very end of its own settings module, so
INSTALLED_APPS and ROOT_URLCONF already hold their final upstream values and can be
extended here. Reading them back from sys.modules is the only way to append rather
than replace: importing openwisp.settings directly would be circular.

Deployed by mounting infra/openwisp-extension/ at
/opt/openwisp/openwisp/configuration/ — see README.md.
"""

import sys

_openwisp_settings = sys.modules["openwisp.settings"]

INSTALLED_APPS = _openwisp_settings.INSTALLED_APPS + [
    "openwisp.configuration.dakar_radius_ext.apps.DakarRadiusExtConfig",
]

ROOT_URLCONF = "openwisp.configuration.custom_urls"
