# Dakar WiFi

Plateforme de Wi-Fi public de la Ville de Dakar : portail captif, API métier,
back-office municipal, et intégration OpenWISP pour le réseau et le RADIUS.

Le cahier des charges fait foi : [`CAHIER_DES_CHARGES_DAKAR_WIFI.md`](CAHIER_DES_CHARGES_DAKAR_WIFI.md).

> **État : Phase 1 — fondations.** Le socle technique est en place (API, portails,
> contrat OpenAPI, CI). Les parcours métier arrivent à partir de la phase 2 :
> voir [le backlog](docs/phase0/03-backlog.md). Les écrans actuels sont des squelettes
> signalés comme tels ; ils interrogent l'API réelle, jamais des données figées.

## Prérequis

| Outil | Version | Installation |
|---|---|---|
| Node.js | ≥ 22 | https://nodejs.org |
| pnpm | ≥ 10 | `npm install -g pnpm` |
| uv | ≥ 0.12 | https://docs.astral.sh/uv/ |
| Docker + Compose | ≥ 24 | https://docs.docker.com |
| GNU Make | — | fourni par la plupart des distributions |

Python 3.13 est téléchargé automatiquement par `uv` : aucune installation manuelle.

## Démarrage

```bash
make setup   # installe les dépendances et crée .env depuis .env.example
make dev     # démarre base, cache, API, worker, puis les deux front-ends
```

| Service | Adresse |
|---|---|
| Portail captif | http://localhost:3000 |
| Back-office | http://localhost:3001 |
| API métier | http://localhost:8000 |
| Documentation OpenAPI | http://localhost:8000/api/v1/docs/ |
| Administration Django | http://localhost:8000/admin/ |

Pour créer des comptes de démonstration (un par rôle du §7, mots de passe générés et
affichés une seule fois) :

```bash
make seed
```

Cette commande **refuse de s'exécuter** lorsque `ENVIRONMENT=production`.

`make help` liste toutes les cibles disponibles.

## Structure

```text
apps/captive-portal/    Portail captif (Astro, statique, mobile-first)
apps/admin-dashboard/   Back-office municipal (Next.js)
services/core-api/      API métier (Django + DRF, Celery)
packages/api-client/    Client TypeScript généré depuis OpenAPI, partagé
packages/ui/            Composants React du back-office
packages/config/        Configurations TypeScript partagées
infra/compose/          Développement local uniquement (jamais la production)
docs/adr/               Décisions d'architecture
docs/phase0/            Diagnostic, backlog, risques, traçabilité
scripts/                Outillage (budget de performance…)
```

## Contrat d'API

Le schéma OpenAPI est la source de vérité du client TypeScript. Après toute
modification d'un endpoint :

```bash
make openapi   # régénère docs/api/openapi.yaml puis packages/api-client/src/schema.d.ts
```

La CI échoue si le dépôt n'est pas à jour vis-à-vis du code.
Ne jamais modifier `packages/api-client/src/schema.d.ts` à la main.

## Vérifications

```bash
make check   # lint + types + tests, comme la CI
make test    # tests seuls (pytest et vitest)
make lint
make typecheck
```

La CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) ajoute la détection de
secrets, l'analyse des dépendances, la construction des images et le contrôle du budget
de performance du portail.

## Secrets

Aucun secret réel ne doit être committé. `.env` est ignoré par git ; `.env.example`
ne contient que des valeurs fictives. Les secrets de staging et de production
proviennent d'un coffre externe et ne sont jamais partagés entre environnements.

## Deux stacks front-end, et pourquoi

Le portail captif est en **Astro** et n'expédie aucun runtime de framework : 0,6 Ko de
JavaScript, contre 169,9 Ko mesurés avec Next.js pour la même page. Il est conçu pour un
Android d'entrée de gamme sur réseau lent, dans un mini-navigateur captif.

Le back-office reste en **Next.js/React** : usage bureau, réseau d'entreprise, écrans
riches — le budget du §12.1 ne s'y applique pas.

Ce qu'ils partagent est `packages/api-client`, qui porte la sécurité de type sur le
contrat d'API. Détail et mesures : [ADR-0005](docs/adr/0005-budget-portail-captif.md).

Toute interactivité ajoutée au portail s'écrit d'abord en TypeScript simple. Une île de
framework ne s'introduit que si un écran le justifie, et son coût se mesure :

```bash
node scripts/check-bundle-budget.mjs apps/captive-portal 150
```

## Points ouverts

- [ADR-0006](docs/adr/0006-integration-openwisp.md) — l'API REST d'OpenWISP ne permet ni
  d'affecter un groupe RADIUS à un usager, ni de forcer une déconnexion. L'activation de
  forfait après paiement en dépend : **décision requise avant la phase 5**. Les phases 2
  à 4 ne sont pas bloquées (elles s'appuient sur `MockNetworkProvider`).
  Mesures et méthode : [spike OpenWISP](docs/phase0/06-spike-openwisp.md).
- [Questions bloquantes pour la production](CAHIER_DES_CHARGES_DAKAR_WIFI.md#22-questions-à-valider-avant-la-production) — 19 questions (§22).
