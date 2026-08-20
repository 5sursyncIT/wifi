# Phase 6 — Vouchers, sponsors et finance

- Date : 2026-08-20
- Statut : conception validée, implémentation en cours
- Sources : cahier des charges v1.2 §8.5, §8.6, §8.11, §8.13, §9, §10.1, §13.4, §16.1, §16.2, §17, §18
- Décisions antérieures : ADR-0003 (langue), ADR-0004 (paiement), spec Phase 4
  (outbox, statuts `refunded`), spec Phase 5 (NetworkProvider)
- Backlog couvert : DW-P6-01, DW-P6-02, DW-P6-03 ; DW-P6-04 en version lite
  (listes admin + CSV, pas de graphiques)
- Critères d'acceptation visés : §17 nos 8 (partiel partenaire), 9, 11, 12

---

## 1. Le problème que cette phase résout

Les phases 3 et 4 donnent un droit par attribution gratuite ou par achat. Il
manque le troisième canal du MVP : un code distribué (événement, partenaire,
guichet). Il manque aussi le geste financier irréversible — remboursement —
et la capacité de rapprocher les encaissements locaux avec le prestataire.

Un coupon consommé puis un OpenWISP down ne doit pas faire perdre le droit :
même garantie que l'achat, même outbox `entitlement.activate`.

### 1.1 La règle structurante

Le code en clair n'existe qu'une fois, à l'émission. En base : `code_hash`
(HMAC-SHA256 + pepper dédié). Les logs, l'admin et les exports n'affichent
qu'un préfixe de 4 caractères. La rédemption commit le droit **avant** tout
appel réseau.

### 1.2 Décisions figées (approche A)

- App `promotions` : Sponsor, Campaign, VoucherBatch, Voucher, VoucherRedemption.
- App `billing` : Refund, ReconciliationRun, export CSV, `refund()` du mock.
- Vue partenaire : filtre queryset Django admin, pas de portail Next.js.
- Tableaux de bord : listes + CSV audités, fuseau `Africa/Dakar`.
- Campagne finance un lot de vouchers ; elle ne remplace pas `ZoneFreePolicy`.
- Un remboursement n'annule pas le droit d'accès ; révocation séparée.

---

## 2. Périmètre

### 2.1 Livré

| Item | Contenu |
|---|---|
| DW-P6-01 | Lots, codes hachés, `POST /api/v1/vouchers/redeem`, révocation, audit, portail |
| DW-P6-02 | Sponsor, Campaign, `partner_user`, queryset restreint, pas de PII citoyen |
| DW-P6-03 | `Refund`, transitions d'ordre, rapprochement mock, export CSV audité |
| DW-P6-04 lite | Agrégats dans `totals_json` et listes admin filtrables |

### 2.2 Hors périmètre

| Sujet | Raison |
|---|---|
| Portail partenaire Next.js | DW-P2-06 encore partiel |
| Graphiques / BI | Agrégats recalculables suffisent au MVP |
| Quota gratuit financé par campagne | `ZoneFreePolicy` inchangé |
| Connecteurs de paiement réels | Phase 7 |
| Accounting RADIUS local | DW-P5-04 reporté |

---

## 3. Frontières de code

```
apps/promotions/
├── models.py        Sponsor, Campaign, VoucherBatch, Voucher, VoucherRedemption
├── codes.py         normalize, hash, generate, issue_batch, revoke
├── redeem.py        redeem_voucher() + VoucherRefused
├── views.py         POST /api/v1/vouchers/redeem
├── serializers.py
├── urls.py
├── admin.py         émission CSV unique, révocation, scope partenaire
└── tests/

apps/billing/
├── models.py        + Refund, ReconciliationRun
├── refunds.py       refund_payment()
├── reconciliation.py run_reconciliation()
├── exports.py       payments_csv()
├── orders.py        transitions paid → partially_refunded / refunded
└── providers/mock.py refund() simulé

apps/access/models.py
└── Entitlement.voucher  FK nullable vers promotions.Voucher
```

`VOUCHER_HASH_PEPPER` est déjà dans `.env.example`. Il est lu dans les settings,
distinct de `OTP_HASH_PEPPER`.

---

## 4. Modèle de données

UUID, horodatages UTC. Montants entiers XOF.

### 4.1 Sponsor

| Champ | Notes |
|---|---|
| `name` | |
| `status` | `draft` / `active` / `suspended` |
| `contact_data` | JSON (email, téléphone) |
| `partner_user` | OneToOne nullable vers `auth.User` |

### 4.2 Campaign

| Champ | Notes |
|---|---|
| `sponsor` | FK PROTECT |
| `name` | |
| `start_at`, `end_at` | |
| `status` | `draft` / `active` / `ended` / `cancelled` |
| `zones` | M2M (`zone_scope` du §9) |
| `budget_xof` | entier nullable, informatif |

### 4.3 VoucherBatch

| Champ | Notes |
|---|---|
| `plan_version` | FK PROTECT, obligatoire |
| `campaign` | FK SET_NULL, optionnelle |
| `zone` | FK PROTECT, optionnelle ; vide = zones de l'offre |
| `quantity` | nombre de codes à émettre |
| `max_uses` | défaut 1, recopié sur chaque voucher |
| `expires_at` | DateTime |
| `codes_exported_at` | null tant que le CSV unique n'a pas été servi |

Un lot déjà pourvu de vouchers ne peut plus être émis.

### 4.4 Voucher

| Champ | Notes |
|---|---|
| `batch` | FK CASCADE |
| `code_hash` | unique, HMAC-SHA256 |
| `prefix` | 4 caractères Crockford, searchable |
| `max_uses`, `uses_count` | |
| `status` | `unused` / `active` / `exhausted` / `expired` / `revoked` |

`active` = au moins une utilisation, encore des usages restants.

### 4.5 VoucherRedemption

Trace d'une consommation réussie (idempotence + unicité citoyen/code).

| Champ | Notes |
|---|---|
| `voucher` | FK PROTECT |
| `citizen` | FK PROTECT |
| `entitlement` | OneToOne |
| `idempotency_key` | |

Contraintes : `Unique(citizen, idempotency_key)`, `Unique(citizen, voucher)`.

### 4.6 Entitlement

FK optionnelle `voucher`. `source=voucher` à la rédemption. L'activation
réutilise `entitlement.activate`.

### 4.7 Refund

| Champ | Notes |
|---|---|
| `payment` | FK PROTECT |
| `amount_xof` | > 0 ; somme des remboursements d'un paiement ≤ `payment.amount_xof` |
| `reason` | texte |
| `requested_by` | FK User PROTECT |
| `status` | `requested` / `succeeded` / `failed` |
| `external_reference` | |
| `processed_at` | |

### 4.8 ReconciliationRun

| Champ | Notes |
|---|---|
| `provider` | |
| `period_start`, `period_end` | |
| `status` | `running` / `balanced` / `mismatch` / `failed` |
| `totals_json` | `local_succeeded_xof`, `provider_succeeded_xof`, `refunded_xof`, `mismatch_count`, `mismatches` |

---

## 5. Codes

Alphabet Crockford `0123456789ABCDEFGHJKMNPQRSTVWXYZ`, 12 caractères, affichage
`XXXX-XXXX-XXXX`. Normalisation : majuscules, tirets et espaces retirés.
`prefix` = 4 premiers caractères normalisés.

`issue_batch(batch) -> list[str]` crée les lignes hachées et retourne les clairs.
L'action admin sert le CSV et pose `codes_exported_at` dans la même requête.
Réémission refusée.

---

## 6. Rédemption

`POST /api/v1/vouchers/redeem`

- Auth JWT citoyen, `Idempotency-Key` obligatoire (max 100).
- Corps : `{ "code", "nas_id" }`. Zone uniquement via `resolve_portal_context`.
- Limitation : 10 tentatives / citoyen / 15 min (cache). Échec ≠ incrément `uses_count`.

Dans une transaction, `select_for_update` sur le voucher :

1. Replay `(citizen, idempotency_key)` → entitlement existant, 200.
2. Compte inutilisable → `account_unusable`.
3. Hash introuvable → `voucher_not_found` (ne pas distinguer révoqué d'inexistant
   pour un attaquant qui brute-force ; **exception** : un code trouvé mais révoqué /
   expiré / épuisé renvoie le motif précis — tests §16.1).
4. `revoked` / `expired` / `batch.expires_at` passé / `exhausted` → codes stables.
5. Campagne présente : doit être `active` et dans `[start_at, end_at]`.
6. Zone : si `batch.zone`, égalité ; si campagne.zones non vide, appartenance ;
   l'offre doit être proposée dans la zone.
7. `Unique(citizen, voucher)` déjà tenu → `voucher_already_used`.
8. Sinon : `uses_count += 1`, statut `active` ou `exhausted`, entitlement
   `pending_activation`, redemption, outbox, audit `voucher.redeem`.

Réponse 201 = `EntitlementSerializer`. Puis drain outbox (comme le webhook).

---

## 7. Admin et partenaire

- `AuditedModelAdmin` sur Sponsor, Campaign, VoucherBatch.
- Voucher : pas d'ajout manuel ; action révoquer.
- Lot : action « Émettre les codes » → CSV `prefix,code` une fois.
- Révocation de lot : `unused` et `active` → `revoked` ; `exhausted` inchangé.
- Partenaire : `get_queryset` limité à `campaign.sponsor.partner_user == request.user`.
  Pas de `search_fields` sur `citizen__phone_e164`. Pas d'export citoyen.
- Rôles seed : commercial (sponsor/campagne/lot add+change, voucher view) ;
  partenaire (view scoped) ; financier (refund, reconciliation, export) ;
  auditeur (view) ; admin_ville (promotions).

---

## 8. Finance

`refund_payment(payment, amount_xof, reason, actor)` :

- Paiement `succeeded` uniquement.
- Somme des refunds `succeeded` + montant ≤ `payment.amount_xof`.
- Appel `provider.refund` **après** création de la ligne `requested` (comme
  l'ordre commit avant le prestataire). Succès → `succeeded` + transition
  d'ordre. Échec → `failed`. Audit `payment.refund`. Pas de révocation d'entitlement.

Mock : `refund()` pose un `RefundResult` `succeeded` et mémorise le montant
remboursé pour `get_payment_status` / le rapprochement.

`run_reconciliation(provider, period_start, period_end)` compare chaque
paiement `succeeded` de la période via `get_payment_status`. Écart →
`mismatch`. Recalculable.

Export CSV (action admin sur Payment) : `order_number`, `paid_at` en
`Africa/Dakar`, `amount_xof`, `fees_xof`, `provider`, `status`, `zone_code`,
`plan_code`. Pas de téléphone, pas de MAC. Audit `payment.export`.

Transitions d'ordre : `paid` → `partially_refunded` | `refunded` ;
`partially_refunded` → `partially_refunded` | `refunded`.

---

## 9. Portail

Lien « J'ai un coupon » sur l'écran des offres. Parcours identification OTP
existant, puis champ code, puis `redeemVoucher`. Messages FR pour les codes
d'erreur. Jamais le code en clair dans un log client.

---

## 10. Tests obligatoires

- Code stocké haché, clair absent de la ligne.
- Voucher valide → entitlement `source=voucher` + outbox.
- Expiré, révoqué, déjà consommé, zone mismatch, campagne inactive.
- Replay Idempotency-Key : un seul entitlement.
- Deux citoyens, un code `max_uses=1` : le second est refusé.
- Brute-force : 11e tentative → `rate_limited`, `uses_count` inchangé.
- OpenWISP down après rédemption : voucher consommé, outbox pending.
- Partenaire : ne voit pas la campagne d'un autre sponsor.
- Refund partiel puis total ; trop-perçu refusé.
- Rapprochement équilibré vs écart.
- Export CSV sans `phone_e164` ; une ligne d'audit.

---

## 11. Données de démonstration

Sponsor « Partenaire Démonstration », campagne sur la zone hybride, lot de 5
codes reproductibles `DEMO-TEST-0001` … `DEMO-TEST-0005`, affichés une fois
par `seed_demo_data` en local, étiquetés mock. `demo_partenaire` lié à
`partner_user`.
