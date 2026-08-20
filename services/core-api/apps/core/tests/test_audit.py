"""Append-only administrative audit log (cahier des charges §1 rule 12, §13.4)."""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.billing.admin import OrderAdmin, PaymentAdmin, WebhookEventAdmin
from apps.billing.models import Order, Payment, WebhookEvent
from apps.catalog.admin import PlanAdmin
from apps.catalog.models import Plan
from apps.core.admin import AuditLogAdmin
from apps.core.audit import record_audit
from apps.core.models import AuditLog
from apps.network.models import Organization


@pytest.mark.django_db
def test_record_audit_stores_actor_action_and_target():
    actor = get_user_model().objects.create_user("auditor", password="x")
    organization = Organization.objects.create(name="Ville")

    record_audit(
        actor=actor,
        action="change",
        target=organization,
        before={"name": "old"},
        after={"name": "Ville"},
    )

    entry = AuditLog.objects.get()
    assert entry.actor_id == actor.pk
    assert entry.action == "change"
    assert entry.target_type == "network.organization"
    assert entry.target_id == str(organization.pk)
    assert entry.before_json == {"name": "old"}
    assert entry.after_json == {"name": "Ville"}


@pytest.mark.django_db
def test_an_audit_row_cannot_be_updated_or_deleted():
    organization = Organization.objects.create(name="Ville")
    record_audit(actor=None, action="create", target=organization, after={"name": "Ville"})
    entry = AuditLog.objects.get()

    entry.action = "tampered"
    with pytest.raises(ValueError, match="append-only"):
        entry.save()

    with pytest.raises(ValueError, match="cannot be deleted"):
        entry.delete()

    assert AuditLog.objects.get().action == "create"


@pytest.mark.django_db
def test_audit_log_admin_is_read_only():
    admin = AuditLogAdmin(AuditLog, AdminSite())
    request = RequestFactory().get("/")
    request.user = get_user_model().objects.create_superuser("root", "r@example.invalid", "x")

    assert admin.has_add_permission(request) is False
    assert admin.has_change_permission(request) is False
    assert admin.has_delete_permission(request) is False
    assert admin.has_view_permission(request) is True


@pytest.mark.django_db
def test_orders_payments_and_webhooks_cannot_be_deleted_in_admin():
    request = RequestFactory().get("/")
    request.user = get_user_model().objects.create_superuser("root", "r@example.invalid", "x")

    assert OrderAdmin(Order, AdminSite()).has_delete_permission(request) is False
    assert PaymentAdmin(Payment, AdminSite()).has_delete_permission(request) is False
    assert WebhookEventAdmin(WebhookEvent, AdminSite()).has_delete_permission(request) is False


@pytest.mark.django_db
def test_saving_a_plan_in_admin_writes_an_audit_row():
    request = RequestFactory().post("/")
    request.user = get_user_model().objects.create_superuser("root", "r@example.invalid", "x")
    plan = Plan(code="demo", name="Démo", type=Plan.Type.FREE)

    PlanAdmin(Plan, AdminSite()).save_model(request, plan, form=None, change=False)

    entry = AuditLog.objects.get()
    assert entry.action == "create"
    assert entry.target_type == "catalog.plan"
    assert entry.actor_id == request.user.pk
    assert entry.after_json["code"] == "demo"
