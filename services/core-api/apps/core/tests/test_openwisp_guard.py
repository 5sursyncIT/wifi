import pytest
from django.core.exceptions import ImproperlyConfigured

from config.openwisp_guard import assert_openwisp_ready


def test_mock_provider_skips_the_guard():
    assert_openwisp_ready("mock", "https://openwisp.example.invalid", "change-me")


def test_openwisp_with_sentinels_is_rejected():
    with pytest.raises(ImproperlyConfigured):
        assert_openwisp_ready("openwisp", "https://openwisp.example.invalid", "change-me")


def test_openwisp_with_real_values_passes():
    assert_openwisp_ready("openwisp", "https://radius.ville.dakar.sn", "not-a-sentinel")
