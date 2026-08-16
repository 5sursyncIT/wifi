import pytest

from apps.catalog.models import PlanVersionIsImmutable


@pytest.mark.django_db
def test_saved_plan_version_refuses_any_change(plan_version):
    plan_version.price_xof = 99_000

    with pytest.raises(PlanVersionIsImmutable):
        plan_version.save()


@pytest.mark.django_db
def test_refused_change_is_not_persisted(plan_version):
    plan_version.price_xof = 99_000

    with pytest.raises(PlanVersionIsImmutable):
        plan_version.save()

    plan_version.refresh_from_db()
    assert plan_version.price_xof == 500
