import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError

EXPECTED_ROLES = {
    "superadmin",
    "admin_ville",
    "exploitant_reseau",
    "responsable_commercial",
    "responsable_financier",
    "agent_support",
    "auditeur",
    "partenaire",
}


@pytest.mark.django_db
def test_seed_demo_data_refuses_to_run_in_production(settings):
    settings.ENVIRONMENT = "production"

    with pytest.raises(CommandError, match="production"):
        call_command("seed_demo_data")


@pytest.mark.django_db
def test_seed_demo_data_creates_a_group_per_internal_role():
    call_command("seed_demo_data")

    assert EXPECTED_ROLES <= set(Group.objects.values_list("name", flat=True))


@pytest.mark.django_db
def test_seed_demo_data_can_be_run_twice_without_duplicating_groups():
    call_command("seed_demo_data")
    call_command("seed_demo_data")

    assert Group.objects.filter(name="agent_support").count() == 1


@pytest.mark.django_db
def test_seed_demo_data_creates_an_internal_account_per_role_in_local(settings):
    settings.ENVIRONMENT = "local"

    call_command("seed_demo_data")

    accounts = get_user_model().objects.filter(username__startswith="demo_")
    assert {account.username for account in accounts} == {f"demo_{role}" for role in EXPECTED_ROLES}


@pytest.mark.django_db
def test_seed_demo_data_creates_no_internal_account_outside_local(settings):
    settings.ENVIRONMENT = "staging"

    call_command("seed_demo_data")

    assert not get_user_model().objects.filter(username__startswith="demo_").exists()
