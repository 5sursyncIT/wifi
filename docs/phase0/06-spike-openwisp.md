# Phase 0 — Spike OpenWISP

- Objectif : vérifier **sur les API réelles** les hypothèses structurantes de l'architecture
  avant d'écrire l'adaptateur (`OpenWispClient`).
- Moyen : instance OpenWISP jetable en Docker (docker-openwisp), hors du monorepo,
  détruite après le spike. Rien de ce spike ne part en production.
- Sortie : ADR consignant les résultats, écarts et décisions induites.
- Statut : **à exécuter** (Docker 29.1 disponible localement).

## Hypothèses à vérifier

| # | Hypothèse | Comment la vérifier | Résultat |
|---|---|---|---|
| H1 | L'API REST d'openwisp-radius permet de créer/modifier un utilisateur RADIUS | Appels API sur l'instance jetable | — |
| H2 | Des groupes/profils RADIUS peuvent porter les limites d'un plan (durée, volume, débit, sessions simultanées) | Créer 2 profils types (gratuit, 1 h) et vérifier les attributs | — |
| H3 | Les compteurs de quota (temps/volume) sont consultables par API | Lire la consommation d'un utilisateur de test | — |
| H4 | L'accounting (start/interim/stop) est exposé par API avec identifiants de session dédupliquables | Injecter des paquets accounting de test, lire par API | — |
| H5 | La déconnexion/CoA est déclenchable via l'API ou un mécanisme documenté | Documentation + test si faisable sans matériel | — |
| H6 | Le multi-tenant (organisations) correspond au modèle Ville → sites | Créer une organisation et rattacher les objets | — |
| H7 | L'authentification API (tokens) permet un compte de service à droits limités | Créer le token, tester les permissions | — |

## Déroulé prévu

1. Lancer docker-openwisp en local (dashboard + API + radius), version stable la plus récente.
2. Dérouler H1 → H7 avec `curl`/httpie, en notant chaque requête et réponse utiles.
3. Consigner les écarts (fonction absente, comportement différent, limite de version).
4. Rédiger l'ADR-0005 « Résultats du spike OpenWISP » avec les conséquences sur
   l'interface `NetworkProvider` et le backlog Phase 5.
5. Détruire l'instance (`docker compose down -v`).

## Critère de sortie

Chaque hypothèse a un résultat **Vérifiée / Partiellement / Infirmée** avec preuve
(commande + réponse). Toute hypothèse infirmée déclenche une mise à jour du backlog
et, si structurante, une révision d'ADR.
