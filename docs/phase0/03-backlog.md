# Phase 0 — Backlog découpé

Identifiants `DW-Px-NN` (phase, numéro). Chaque item se termine par ses critères
d'acceptation vérifiables (référence §17 et §24 du cahier des charges).
Le détail fin (sous-tâches) sera tenu dans l'outil de suivi une fois choisi.

## Phase 1 — Fondations du monorepo

| ID | Item | Références |
|---|---|---|
| DW-P1-01 | Structure du monorepo conforme §5.1 (apps, services, packages, infra, docs) | §5.1 |
| DW-P1-02 | `services/core-api` : Django/DRF bootstrapé, settings par environnement, healthcheck | §5.2, §5.3 |
| DW-P1-03 | PostgreSQL + Redis + Celery en Docker Compose local | §5.2 |
| DW-P1-04 | `apps/captive-portal` : Next.js mobile-first, page squelette, budget perf outillé | §12.1 |
| DW-P1-05 | `apps/admin-dashboard` : Next.js, login admin de base | §5.2, D3 |
| DW-P1-06 | OpenAPI 3.1 généré (drf-spectacular) + client TS (`packages/api-client`) | §5.2, D5 |
| DW-P1-07 | CI : lint, types, tests unitaires/intégration, détection de secrets, schéma OpenAPI | §15.3 |
| DW-P1-08 | `.env.example` complet (§20), Makefile, README « démarrage en une commande » | §5.3, §20 |
| DW-P1-09 | Commande de données de démonstration (socle, refus si production) | §21, règle 18 |

## Phase 2 — Sites, zones, plans et portail

| ID | Item |
|---|---|
| DW-P2-01 | Modèles Organization, Site, Zone, Hotspot + migrations + admin |
| DW-P2-02 | Modèles Plan / PlanVersion immuable + statuts de publication (§8.3) |
| DW-P2-03 | Résolution serveur du contexte hotspot, refus des paramètres non autorisés (§8.2) |
| DW-P2-04 | `GET /portal/context` et `GET /portal/plans` |
| DW-P2-05 | UI portail : accueil zone, catalogue des offres, mode repli hotspot mal configuré |
| DW-P2-06 | Back-office : CRUD sites/zones/hotspots/plans avec rôles de base |
| DW-P2-07 | Carte Leaflet/OSM avec clustering et fiche de santé placeholder (§8.9) |

## Phase 3 — Comptes, OTP et accès gratuit

| ID | Item |
|---|---|
| DW-P3-01 | Modèles User, UserDevice (MAC = indice, §8.1), OtpRequest, SmsMessage |
| DW-P3-02 | `MockSmsProvider` + interface SmsProvider |
| DW-P3-03 | Endpoints OTP request/verify/refresh/logout + rate limiting distribué (§13.1) |
| DW-P3-04 | TermsVersion/Consent versionnés (§8.1) |
| DW-P3-05 | Entitlement gratuit + règles de quota par zone (§8.4) |
| DW-P3-06 | `MockNetworkProvider` avec les 7 scénarios du §11.3, interface incluant `assign_plan()` et `disconnect()` ([ADR-0006](../adr/0006-integration-openwisp.md)) |
| DW-P3-07 | E2E Playwright : parcours gratuit complet (critères 1-3 du §17) |

## Phase 4 — Commandes, paiement mock et abonnements

| ID | Item |
|---|---|
| DW-P4-01 | Order + états + TTL `pending` + Idempotency-Key (§8.5) |
| DW-P4-02 | Interface PaymentProvider (push + redirection, ADR-0004) + MockPaymentProvider |
| DW-P4-03 | Webhooks signés : validation, idempotence, historique, post-expiration (§8.5) |
| DW-P4-04 | Entitlement payant + outbox transactionnelle + activation idempotente (§11.2) |
| DW-P4-05 | UI paiement : attente push, sondage statut, repli redirection, reçu |
| DW-P4-06 | E2E : achat complet mock (critères 4-6 du §17) |

## Phase 5 — OpenWISP staging

| ID | Item |
|---|---|
| DW-P5-00 | Durcir l'extension OpenWISP ([ADR-0006](../adr/0006-integration-openwisp.md), maquette dans `infra/openwisp-extension/`) : droits par organisation, tests automatisés, version d'OpenWISP épinglée |
| DW-P5-01 | Instance OpenWISP staging documentée (Ansible) ; configurer `freeradius_allowed_hosts` et `coa_enabled` |
| DW-P5-02 | OpenWispClient (adaptateur §11) + gestion erreurs/retries/circuit breaker |
| DW-P5-03 | Sync utilisateurs/profils RADIUS + réconciliation nocturne ; groupes RADIUS pré-provisionnés référencés par `PlanVersion.radius_profile_ref` |
| DW-P5-04 | Import accounting sans double comptage (§8.8) |
| DW-P5-05 | CoA si supporté + test hotspot de laboratoire |

## Phase 6 — Vouchers, sponsors et finance

| ID | Item |
|---|---|
| DW-P6-01 | VoucherBatch/Voucher hachés + redemption + révocation (§8.6) |
| DW-P6-02 | Sponsor/Campaign + vue partenaire restreinte (§8.11) |
| DW-P6-03 | Rapprochement financier + Refund + exports audités (§8.13) |
| DW-P6-04 | Tableaux de bord technique/usage/finance (§8.13) |

Les phases 7 (connecteurs réels) et 8 (durcissement, pilote terrain) seront détaillées
quand les contrats et accès sandbox seront connus (§18).
