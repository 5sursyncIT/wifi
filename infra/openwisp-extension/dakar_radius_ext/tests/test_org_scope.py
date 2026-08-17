from openwisp.configuration.dakar_radius_ext.org_scope import shares_organization


def test_sharing_one_organization_is_enough():
    assert shares_organization({"a", "b"}, {"b", "c"}) is True


def test_disjoint_organizations_are_denied():
    assert shares_organization({"a"}, {"b"}) is False


def test_empty_sets_are_denied():
    assert shares_organization(set(), {"a"}) is False
    assert shares_organization({"a"}, set()) is False
