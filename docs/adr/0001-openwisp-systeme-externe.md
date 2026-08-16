# ADR-0001 — OpenWISP comme système externe de référence

- Statut : Acceptée
- Date : 2026-08-16
- Source : cahier des charges v1.1, §1 (règles 1-2), §4.3, §11

## Contexte

La plateforme a besoin d'un moteur de gestion réseau (provisionnement, supervision) et
d'AAA/RADIUS (authentification, quotas, accounting, CoA). Développer ces fonctions serait
long, risqué et redondant avec un projet open source mature.

## Décision

- OpenWISP (Controller, Monitoring, RADIUS/FreeRADIUS) est le système de référence pour
  le réseau et l'AAA. Il n'est ni forké, ni modifié dans son cœur.
- Toute interaction passe par ses API officielles, encapsulées dans un adaptateur versionné
  (`OpenWispClient` derrière l'interface `NetworkProvider`).
- La base métier Dakar WiFi n'écrit jamais dans les tables internes d'OpenWISP.
- Un `MockNetworkProvider` implémente la même interface pour le développement et les tests.

## Conséquences

- Les mises à jour d'OpenWISP restent possibles sans conflit avec le code métier.
- Les hypothèses structurantes (quotas par utilisateur, profils RADIUS par plan, CoA,
  lecture de l'accounting) doivent être **vérifiées sur les API réelles** avant d'écrire
  l'adaptateur → spike Phase 0 (voir [06-spike-openwisp](../phase0/06-spike-openwisp.md)).
- La latence et la disponibilité d'OpenWISP deviennent des dépendances externes : outbox
  transactionnelle, retries et réconciliation sont obligatoires (§11.2 du cahier des charges).

## Alternatives écartées

- **Développement AAA maison** : coût et risque disproportionnés, réinvention de FreeRADIUS.
- **Fork d'OpenWISP** : gèle les mises à jour de sécurité, interdit par le cahier des charges.
- **Contrôleur propriétaire seul (ex. UniFi)** : couplage à un constructeur ; l'interface
  `NetworkProvider` garde cette option ouverte en complément (phase ultérieure, feature flag).
