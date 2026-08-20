from typing import Any

from drf_spectacular.generators import SchemaGenerator


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        return schema["components"]["schemas"][name]
    return node


def test_openapi_schema_documents_the_health_response_body():
    schema = SchemaGenerator().get_schema(request=None, public=True)

    content = schema["paths"]["/api/v1/health"]["get"]["responses"]["200"]["content"]
    body = _resolve(schema, content["application/json"]["schema"])

    assert set(body["properties"]) == {"status", "environment", "version", "checks"}


def test_openapi_schema_documents_voucher_redemption():
    schema = SchemaGenerator().get_schema(request=None, public=True)

    assert "/api/v1/vouchers/redeem" in schema["paths"]
    assert "post" in schema["paths"]["/api/v1/vouchers/redeem"]
