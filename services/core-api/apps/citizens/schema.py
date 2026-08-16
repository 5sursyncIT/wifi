"""Describe the citizen bearer scheme to drf-spectacular.

drf-spectacular can only publish an authenticator it recognises. Left undeclared,
CitizenTokenAuthentication is dropped with a warning and the endpoints behind it are
published with no security requirement at all — a generated client would then never
send the token. The extension registers itself on import, which apps.py performs.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CitizenTokenScheme(OpenApiAuthenticationExtension):
    target_class = "apps.citizens.authentication.CitizenTokenAuthentication"
    name = "citizenToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Jeton d'accès citoyen obtenu par /auth/otp/verify puis renouvelé par "
                "/auth/refresh. Distinct de la session d'administration : il n'ouvre "
                "aucun droit dans le back-office (ADR-0007)."
            ),
        }
