"""Append-only audit trail for sensitive administrative actions (§1 rule 12)."""

from __future__ import annotations

from typing import Any

from apps.core.models import AuditLog


def snapshot(instance) -> dict[str, Any]:
    """JSON-safe copy of concrete field values, excluding timestamps."""
    if instance is None:
        return {}
    data: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if field.name in {"created_at", "updated_at"}:
            continue
        value = getattr(instance, field.attname)
        if value is None or isinstance(value, (str, int, float, bool)):
            data[field.name] = value
        else:
            data[field.name] = str(value)
    return data


def record_audit(*, actor, action: str, target, before=None, after=None) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=f"{target._meta.app_label}.{target._meta.model_name}",
        target_id=str(target.pk),
        before_json=before or {},
        after_json=after or {},
    )
