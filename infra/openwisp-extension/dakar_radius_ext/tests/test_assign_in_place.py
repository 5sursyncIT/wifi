from django.contrib.auth import get_user_model
from django.test import TestCase
from openwisp_radius.utils import load_model
from openwisp_users.models import Organization, OrganizationUser
from rest_framework.test import APIClient

from dakar_radius_ext.services import assign_group

RadiusGroup = load_model("RadiusGroup")
RadiusUserGroup = load_model("RadiusUserGroup")
User = get_user_model()


class AssignGroupInPlaceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Ville", slug="ville-test")
        self.other_org = Organization.objects.create(name="Autre", slug="autre-test")
        self.group_a = RadiusGroup.objects.create(
            organization=self.org, name="plan-a"
        )
        self.group_b = RadiusGroup.objects.create(
            organization=self.org, name="plan-b"
        )
        self.user = User.objects.create_user(username="citizen-1", password="x")
        OrganizationUser.objects.create(user=self.user, organization=self.org)
        self.foreign = User.objects.create_user(username="foreign-1", password="x")
        OrganizationUser.objects.create(user=self.foreign, organization=self.other_org)
        self.actor = User.objects.create_user(username="dakar-service", password="x")
        OrganizationUser.objects.create(
            user=self.actor, organization=self.org, is_admin=True
        )

    def test_changing_group_keeps_the_same_membership_row(self):
        first, changed = assign_group(self.user, "plan-a")
        self.assertTrue(changed)
        second, changed = assign_group(self.user, "plan-b")
        self.assertTrue(changed)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.group_id, self.group_b.pk)
        self.assertEqual(RadiusUserGroup.objects.filter(user=self.user).count(), 1)

    def test_same_group_is_a_noop(self):
        first, _ = assign_group(self.user, "plan-a")
        second, changed = assign_group(self.user, "plan-a")
        self.assertFalse(changed)
        self.assertEqual(first.pk, second.pk)

    def test_assign_group_api_forbids_a_foreign_organization(self):
        client = APIClient()
        client.force_authenticate(user=self.actor)
        response = client.post(
            "/api/v1/dakar/radius/assign-group/",
            {"username": "foreign-1", "group_name": "plan-a"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
