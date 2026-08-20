"""Partner scoping in the Django admin (§8.11, §16.2)."""

from datetime import timedelta

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.utils import timezone

from apps.promotions.admin import CampaignAdmin
from apps.promotions.models import Campaign, Sponsor


@pytest.fixture
def partner_group(db):
    group, _ = Group.objects.get_or_create(name="partenaire")
    return group


def test_a_partner_only_sees_their_own_campaigns(django_user_model, partner_group, zone):
    mine = django_user_model.objects.create_user("demo_partenaire", password="x", is_staff=True)
    mine.groups.add(partner_group)
    other = django_user_model.objects.create_user("other_partner", password="x", is_staff=True)
    other.groups.add(partner_group)

    ours = Sponsor.objects.create(name="Nous", status=Sponsor.Status.ACTIVE, partner_user=mine)
    theirs = Sponsor.objects.create(name="Eux", status=Sponsor.Status.ACTIVE, partner_user=other)
    now = timezone.now()
    Campaign.objects.create(
        sponsor=ours,
        name="Notre campagne",
        start_at=now,
        end_at=now + timedelta(days=1),
        status=Campaign.Status.ACTIVE,
    )
    Campaign.objects.create(
        sponsor=theirs,
        name="Leur campagne",
        start_at=now,
        end_at=now + timedelta(days=1),
        status=Campaign.Status.ACTIVE,
    )

    request = RequestFactory().get("/admin/")
    request.user = mine
    queryset = CampaignAdmin(Campaign, AdminSite()).get_queryset(request)

    assert list(queryset.values_list("name", flat=True)) == ["Notre campagne"]


def test_a_superuser_sees_every_campaign(django_user_model, partner_group, zone):
    partner = django_user_model.objects.create_user("p", password="x", is_staff=True)
    partner.groups.add(partner_group)
    admin = django_user_model.objects.create_superuser("admin", password="x")
    sponsor = Sponsor.objects.create(name="S", status=Sponsor.Status.ACTIVE, partner_user=partner)
    now = timezone.now()
    Campaign.objects.create(
        sponsor=sponsor,
        name="C",
        start_at=now,
        end_at=now + timedelta(days=1),
        status=Campaign.Status.ACTIVE,
    )

    request = RequestFactory().get("/admin/")
    request.user = admin
    queryset = CampaignAdmin(Campaign, AdminSite()).get_queryset(request)

    assert queryset.count() == 1
