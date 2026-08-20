"""Voucher codes are unguessable and stored hashed (§8.6, §16.1)."""

import hmac

from apps.promotions.codes import format_code, generate_code, hash_code, normalize_code


def test_normalization_strips_hyphens_spaces_and_case():
    assert normalize_code(" abcd-efgh-ijkm ") == "ABCDEFGHIJKM"


def test_a_formatted_code_is_three_groups_of_four():
    assert format_code("ABCDEFGHIJKM") == "ABCD-EFGH-IJKM"


def test_generated_codes_are_twelve_crockford_characters():
    code = generate_code()
    compact = normalize_code(code)

    assert len(compact) == 12
    assert set(compact) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert code == format_code(compact)


def test_the_cleartext_is_not_the_stored_hash(settings):
    settings.VOUCHER_HASH_PEPPER = "test-pepper-not-for-production-use"
    code = "DEMO-TEST-0001"

    digest = hash_code(code)

    assert digest != code
    assert code not in digest
    assert len(digest) == 64


def test_the_same_code_with_different_formatting_hashes_identically(settings):
    settings.VOUCHER_HASH_PEPPER = "test-pepper-not-for-production-use"

    assert hash_code("DEMO-TEST-0001") == hash_code("demo test 0001")


def test_a_different_pepper_produces_a_different_digest(settings):
    settings.VOUCHER_HASH_PEPPER = "pepper-a"
    first = hash_code("DEMO-TEST-0001")
    settings.VOUCHER_HASH_PEPPER = "pepper-b"

    assert hash_code("DEMO-TEST-0001") != first
    assert hmac.compare_digest(first, first)
