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

| ID | Item | État |
|---|---|---|
| DW-P2-01 | Modèles Organization, Site, Zone, Hotspot + migrations + admin | livré |
| DW-P2-02 | Modèles Plan / PlanVersion immuable + statuts de publication (§8.3) | livré |
| DW-P2-03 | Résolution serveur du contexte hotspot, refus des paramètres non autorisés (§8.2) | livré |
| DW-P2-04 | `GET /portal/context`, `GET /portal/plans`, `GET /public/hotspots` | livré |
| DW-P2-05 | UI portail : accueil zone, catalogue des offres, mode repli hotspot mal configuré | livré |
| DW-P2-06 | Back-office : configuration par l'admin Django ; écrans Next.js dédiés | **partiel** |
| DW-P2-07 | Carte Leaflet/OSM avec clustering et filtre par mode d'accès (§8.9) | livré |
| DW-P2-08 | Incidents réseau : ouverture auto hors-ligne/dégradé, cycle, SLA (§8.10) | livré (lite) |
| DW-P2-09 | i18n portail : français, wolof, anglais (règle 16, ADR-0003) | livré |

**DW-P2-06 — ce qui reste.** La configuration complète (sites, zones, bornes, offres,
versions, incidents) se fait dans l'administration Django. Le back-office Next.js
expose la carte, la liste des sites et le nombre d'incidents ouverts. Les écrans
de configuration dédiés restent à livrer.

**DW-P2-09.** Le portail captive sert le français par défaut (référence fonctionnelle).
Un sélecteur FR / WO / EN bascule l'interface ; le wolof reste court (règle 16).
Pas de `next-intl` : dictionnaire maison, pour tenir le budget JS Astro (ADR-0005).

## Phase 3 — Comptes, OTP et accès gratuit

| ID | Item | État |
|---|---|---|
| DW-P3-01 | Modèles Citizen, CitizenDevice, OtpRequest, SmsMessage, RefreshToken ([ADR-0007](../adr/0007-comptes-citoyens-et-otp.md)) | livré |
| DW-P3-02 | `MockSmsProvider` + interface SmsProvider | livré |
| DW-P3-03 | Endpoints OTP request/verify/refresh/logout + limitation d'abus (§13.1) | livré |
| DW-P3-04 | TermsVersion/Consent versionnés, refus d'activation sans consentement (§8.1) | livré |
| DW-P3-05 | Entitlement gratuit + règles de quota par zone (§8.4) | livré |
| DW-P3-06 | `MockNetworkProvider` avec les 7 scénarios du §11.3, `assign_plan()` et `disconnect()` | livré |
| DW-P3-07 | E2E Playwright : parcours gratuit complet (critères 1-3 du §17) | livré |
| DW-P3-08 | Export JSON et suppression (anonymisation) du compte (§8.1) | livré |
| DW-P3-09 | `SupportTicket` + `POST /api/v1/support/tickets` + formulaire portail (§8.12) | livré |
| DW-P3-10 | `NetworkSession` locale + `GET /me/sessions` + déconnexion (§8.8, §10.1) | livré (lite) |

**Reste ouvert.** Les appareils (`CitizenDevice`) sont modélisés ; la limite
`max_devices` s'applique lorsque le portail transmet un `device_hint`. La MAC
du client n'est pas encore fournie par la passerelle. L'import accounting RADIUS
(octets réels, anti double comptage) reste DW-P5-04.

## Phase 4 — Commandes, paiement mock et abonnements

| ID | Item | État |
|---|---|---|
| DW-P4-01 | Order + états + TTL `pending` + Idempotency-Key (§8.5) | livré |
| DW-P4-02 | Interface PaymentProvider (push + redirection, ADR-0004) + MockPaymentProvider | livré |
| DW-P4-03 | Webhooks signés : validation, idempotence, historique, post-expiration (§8.5) | livré |
| DW-P4-04 | Entitlement payant + outbox transactionnelle + activation idempotente (§11.2) | livré |
| DW-P4-05 | UI paiement : attente push, sondage statut, repli redirection, reçu | livré |
| DW-P4-06 | E2E : achat complet mock (critères 4-6 du §17) | livré |

## Phase 5 — OpenWISP staging

| ID | Item | État |
|---|---|---|
| DW-P5-00 | Durcir l'extension OpenWISP ([ADR-0006](../adr/0006-integration-openwisp.md), maquette dans `infra/openwisp-extension/`) : droits par organisation, tests automatisés, version d'OpenWISP épinglée | livré |
| DW-P5-01 | Instance OpenWISP staging documentée (Ansible) ; configurer `freeradius_allowed_hosts` et `coa_enabled` | reporté, hors itération adapter-docker |
| DW-P5-02 | OpenWispClient (adaptateur §11) + gestion erreurs/retries/circuit breaker | livré |
| DW-P5-03 | Sync utilisateurs/profils RADIUS + réconciliation nocturne ; groupes RADIUS pré-provisionnés référencés par `PlanVersion.radius_profile_ref` | livré (lite) |
| DW-P5-04 | Import accounting sans double comptage (§8.8) | reporté, hors itération adapter-docker ; sessions locales + disconnect API livrés (DW-P3-10) |
| DW-P5-05 | CoA si supporté + test hotspot de laboratoire | reporté, hors itération adapter-docker |

- **DW-P5-00 — validation du laboratoire.** Les imports des tests de l'extension
  sont alignés sur le paquet OpenWISP. L'exécution réelle de
  `make test-openwisp` reste toutefois bloquée sur cet hôte par le chevauchement
  du sous-réseau Docker `172.18.0.0/16` avec `winboat_default`.
- **DW-P5-02 — idempotence CoA.** L'adaptateur OpenWISP doit traiter la
  réaffectation du même groupe RADIUS comme un no-op : l'outbox de phase 4 est
  at-least-once et un worker peut mourir après `assign_plan()` mais avant le
  passage de l'Entitlement à `ACTIVE`.

## Phase 6 — Vouchers, sponsors et finance

| ID | Item | État |
|---|---|---|
| DW-P6-01 | VoucherBatch/Voucher hachés + redemption + révocation (§8.6) | livré |
| DW-P6-02 | Sponsor/Campaign + vue partenaire restreinte (§8.11) | livré |
| DW-P6-03 | Rapprochement financier + Refund + exports audités (§8.13) | livré |
| DW-P6-04 | Tableaux de bord technique/usage/finance (§8.13) | **lite** (listes admin + CSV, pas de graphiques) |

Les phases 7 (connecteurs réels) et 8 (durcissement, pilote terrain) seront détaillées
quand les contrats et accès sandbox seront connus (§18).
