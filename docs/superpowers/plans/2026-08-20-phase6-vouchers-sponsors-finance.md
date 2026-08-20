# Phase 6 — Vouchers, sponsors et finance — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre l'émission et la rédemption de coupons hachés, les campagnes sponsor, les remboursements et un rapprochement exportable, sans perdre un droit si le réseau est down.

**Architecture:** App `promotions` pour sponsors/campagnes/vouchers ; finance dans `billing`. La rédemption commit entitlement + outbox `entitlement.activate` avant tout appel `NetworkProvider`. Les codes en clair n'existent qu'à l'émission.

**Tech Stack:** Django 5, DRF, HMAC-SHA256, Celery outbox existante, admin Django, Astro portail, pytest.

**Spec:** `docs/superpowers/specs/2026-08-20-phase6-vouchers-sponsors-finance-design.md`

## Global Constraints

- Identifiants EN, UI et docs FR (ADR-0003).
- Montants entiers XOF, jamais de décimaux.
- Aucun code voucher complet dans les logs.
- `VOUCHER_HASH_PEPPER` distinct de `OTP_HASH_PEPPER`.
- Zone uniquement via `nas_id` / `resolve_portal_context`.
- Tests pytest sur PostgreSQL réel (`make test-api`).
- Ne pas committer sauf demande explicite.

---

### Task 1: Codes et modèles promotions

**Files:**
- Create: `services/core-api/apps/promotions/` (apps, models, codes, admin stub, tests)
- Modify: `services/core-api/config/settings/base.py` (INSTALLED_APPS, pepper, rate limits)
- Modify: `services/core-api/apps/access/models.py` (`Entitlement.voucher`)
- Test: `services/core-api/apps/promotions/tests/test_codes.py`, `test_models.py`

**Produces:** `hash_code(code: str) -> str`, `generate_code() -> str`, `normalize_code(code: str) -> str`, `issue_batch(batch) -> list[str]`, models Sponsor/Campaign/VoucherBatch/Voucher/VoucherRedemption.

- [ ] Tests de hachage et d'émission (TDD)
- [ ] Modèles + migration
- [ ] `issue_batch` / `revoke_voucher` / `revoke_batch`

### Task 2: Rédemption métier et API

**Files:**
- Create: `redeem.py`, `views.py`, `serializers.py`, `urls.py`
- Modify: `config/urls.py`
- Test: `tests/test_redeem.py`, `tests/test_redeem_api.py`

**Produces:** `redeem_voucher(citizen, code, zone, idempotency_key) -> Entitlement`, `VoucherRefused(reason, message)`, `POST /api/v1/vouchers/redeem`.

- [ ] Tests §16.1 (valide, expiré, révoqué, consommé, zone, campagne, replay, rate limit, outbox)
- [ ] Implémentation + drain outbox

### Task 3: Admin, partenaire, RBAC, seed

**Files:**
- Modify: `promotions/admin.py`, `seed_demo_data.py`, `test_seed_demo_data.py`
- Test: `promotions/tests/test_admin_scope.py`

**Produces:** CSV d'émission unique, révocation auditée, queryset partenaire, permissions, 5 codes DEMO.

### Task 4: Refund, rapprochement, export

**Files:**
- Modify: `billing/models.py`, `orders.py`, `providers/mock.py`, `admin.py`
- Create: `billing/refunds.py`, `reconciliation.py`, `exports.py`
- Test: `billing/tests/test_refunds.py`, `test_reconciliation.py`, `test_exports.py`

**Produces:** `refund_payment(...)`, `run_reconciliation(...)`, `payments_csv(...)`.

### Task 5: Portail, client TS, OpenAPI, docs

**Files:**
- Modify: `packages/api-client/src/index.ts`, `apps/captive-portal/src/lib/portal.ts`
- Modify: `docs/api/openapi.yaml` (via `make openapi`), backlog, matrice
- Test: `apps/captive-portal/src/lib/portal.test.ts` si existant ; tests client si existant

**Produces:** `redeemVoucher(nasId, code, idempotencyKey)`, UI coupon, schéma à jour.
