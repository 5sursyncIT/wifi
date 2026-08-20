"""Citizen-facing copy: French is the source of truth, wolof and English overlay it."""

from __future__ import annotations

LOCALES = ("fr", "wo", "en")


def parse_locale(value: str | None) -> str:
    if not value:
        return "fr"
    prefix = value.strip().lower()[:2]
    return prefix if prefix in LOCALES else "fr"


def locale_from_request(request) -> str:
    query = request.query_params.get("lang")
    if query:
        return parse_locale(query)
    header = request.headers.get("Accept-Language", "")
    if header:
        return parse_locale(header.split(",", 1)[0].split(";", 1)[0])
    return "fr"


def localized(instance, field: str, locale: str) -> str:
    french = getattr(instance, field) or ""
    if locale == "fr":
        return french
    table = getattr(instance, "i18n", None) or {}
    overlay = table.get(locale) if isinstance(table, dict) else None
    if not isinstance(overlay, dict):
        return french
    value = overlay.get(field)
    return value if value else french
