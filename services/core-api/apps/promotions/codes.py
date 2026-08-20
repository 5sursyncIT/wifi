"""Generation and hashing of voucher codes (cahier des charges §8.6).

The cleartext exists only at issuance. Lookup is by HMAC digest, so a database
dump does not hand out usable codes. A dedicated pepper keeps a stolen OTP
pepper from unlocking the voucher table.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 12


def normalize_code(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def format_code(normalized: str) -> str:
    compact = normalize_code(normalized)
    return f"{compact[0:4]}-{compact[4:8]}-{compact[8:12]}"


def prefix_of(code: str) -> str:
    return normalize_code(code)[:4]


def hash_code(code: str) -> str:
    return hmac.new(
        settings.VOUCHER_HASH_PEPPER.encode(),
        normalize_code(code).encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_code() -> str:
    compact = "".join(secrets.choice(CROCKFORD) for _ in range(CODE_LENGTH))
    return format_code(compact)


def issue_batch(batch) -> list[str]:
    """Create hashed voucher rows and return the cleartexts once.

    A second call is refused: the cleartexts of the first run are gone.
    """
    from apps.promotions.models import Voucher

    if batch.vouchers.exists():
        raise ValueError("This batch has already been issued.")

    codes: list[str] = []
    seen: set[str] = set()
    while len(codes) < batch.quantity:
        code = generate_code()
        digest = hash_code(code)
        if digest in seen:
            continue
        seen.add(digest)
        codes.append(code)

    Voucher.objects.bulk_create(
        [
            Voucher(
                batch=batch,
                code_hash=hash_code(code),
                prefix=prefix_of(code),
                max_uses=batch.max_uses,
            )
            for code in codes
        ]
    )
    return codes


def import_codes(batch, codes: list[str]) -> list[str]:
    """Seed-friendly issuance of known demonstration codes."""
    from apps.promotions.models import Voucher

    if batch.vouchers.exists():
        return []
    Voucher.objects.bulk_create(
        [
            Voucher(
                batch=batch,
                code_hash=hash_code(code),
                prefix=prefix_of(code),
                max_uses=batch.max_uses,
            )
            for code in codes
        ]
    )
    return list(codes)


def revoke_voucher(voucher) -> None:
    from apps.promotions.models import Voucher

    if voucher.status == Voucher.Status.EXHAUSTED:
        return
    voucher.status = Voucher.Status.REVOKED
    voucher.save(update_fields=["status", "updated_at"])


def revoke_batch(batch) -> int:
    from apps.promotions.models import Voucher

    return batch.vouchers.exclude(status=Voucher.Status.EXHAUSTED).update(
        status=Voucher.Status.REVOKED
    )
