"""The OpenAPI contract must describe the citizen bearer scheme (cahier des charges §10.1).

Without it drf-spectacular silently drops the authenticator it cannot resolve, and the
endpoints that require a citizen token are published as if they needed nothing at all —
so a client generated from the contract never sends the token.
"""

import pytest
from drf_spectacular.generators import SchemaGenerator

SCHEME_NAME = "citizenToken"

# Every endpoint behind CitizenTokenAuthentication.
PROTECTED = [
    ("/api/v1/auth/logout", "post"),
    ("/api/v1/me", "get"),
    ("/api/v1/me/entitlements", "get"),
    ("/api/v1/me/export", "get"),
    ("/api/v1/me/deletion", "post"),
    ("/api/v1/me/sessions", "get"),
    ("/api/v1/me/sessions/{session_id}/disconnect", "post"),
    ("/api/v1/portal/free-access", "post"),
    ("/api/v1/orders", "post"),
    ("/api/v1/orders/{order_id}", "get"),
    ("/api/v1/orders/{order_id}/receipt", "get"),
]

# Reachable without a token; the contract must not demand one.
PUBLIC = [
    ("/api/v1/auth/otp/request", "post"),
    ("/api/v1/auth/otp/verify", "post"),
    ("/api/v1/portal/terms", "get"),
    ("/api/v1/webhooks/payments/{provider}", "post"),
    ("/api/v1/support/tickets", "post"),
]


@pytest.fixture(scope="module")
def schema():
    return SchemaGenerator().get_schema(request=None, public=True)


def test_contract_declares_the_citizen_bearer_scheme(schema):
    definition = schema["components"]["securitySchemes"].get(SCHEME_NAME)

    assert definition is not None, "le schéma d'authentification citoyen est absent"
    assert definition["type"] == "http"
    assert definition["scheme"] == "bearer"


def test_order_creation_requires_the_idempotency_header(schema):
    parameters = schema["paths"]["/api/v1/orders"]["post"].get("parameters", [])
    parameter = next(
        (item for item in parameters if item["name"] == "Idempotency-Key"),
        None,
    )

    assert parameter is not None
    assert parameter["in"] == "header"
    assert parameter["required"] is True
    assert parameter["schema"] == {"type": "string", "maxLength": 100}


@pytest.mark.parametrize(("path", "method"), PROTECTED)
def test_protected_endpoints_require_the_citizen_token(schema, path, method):
    security = schema["paths"][path][method].get("security")

    assert security is not None, (
        f"{method.upper()} {path} est publié sans exigence d'authentification"
    )
    assert {SCHEME_NAME: []} in security, f"{method.upper()} {path} n'exige pas le jeton citoyen"


@pytest.mark.parametrize(("path", "method"), PROTECTED)
def test_protected_endpoints_do_not_offer_an_anonymous_alternative(schema, path, method):
    # An empty requirement means "no authentication is also acceptable". Publishing it
    # next to the token would tell a client the token is optional on these endpoints.
    assert {} not in schema["paths"][path][method]["security"]


@pytest.mark.parametrize(("path", "method"), PUBLIC)
def test_public_endpoints_stay_reachable_without_a_token(schema, path, method):
    security = schema["paths"][path][method].get("security")

    assert security is None or {} in security, (
        f"{method.upper()} {path} est public mais le contrat exige une authentification"
    )
