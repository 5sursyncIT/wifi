# Dakar WiFi

Plateforme de Wi-Fi public de la Ville de Dakar : portail captif, API métier,
back-office municipal, et intégration OpenWISP pour le réseau et le RADIUS.

Le cahier des charges fait foi : [`CAHIER_DES_CHARGES_DAKAR_WIFI.md`](CAHIER_DES_CHARGES_DAKAR_WIFI.md).

> **État : Phase 6 livrée ; comptes citoyens, incidents réseau et i18n portail en place.**
> Un citoyen s'inscrit par OTP, accepte les conditions, puis obtient l'accès gratuit,
> achète une offre payante, ou saisit un coupon. Il peut exporter ses données,
> supprimer son compte (anonymisation, pièces financières conservées), ouvrir un
> ticket d'aide et se déconnecter. Une borne hors ligne ou dégradée ouvre un
> incident (cycle P1–P4, délais de prise en charge). Les codes sont hachés ; la
> rédemption passe par la même outbox que l'achat. Sponsors et campagnes se gèrent
> dans l'admin Django, avec une vue partenaire limitée à ses campagnes.
> Remboursements, rapprochement mock et export CSV audité (sans téléphone) sont
> disponibles. Les tableaux de bord graphiques restent hors périmètre
> (listes + CSV). Le portail propose le français, le wolof (libellés courts) et
> l'anglais (sélecteur FR / WO / EN), avec les armoiries officielles de la Ville
> ([mairie de Dakar](https://mairiedakar.sn/)). L'adaptateur OpenWISP est livré ;
> le mock reste le défaut.
> Ansible staging, l'import accounting RADIUS et l'essai sur borne réelle sont
> reportés. La Phase 7 (Wave/Orange Money réels) attend les sandboxes (§18).

Pour voir le portail avec les données de démonstration :
`make dev`, puis <http://localhost:3000/?nas_id=demo-nas-001>
(le paramètre est normalement ajouté par la passerelle Wi-Fi).

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
En local, elle imprime aussi cinq coupons mock `DEMO-TEST-0001` … `DEMO-TEST-0005`
(une seule fois, étiquetés comme tels).

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
make e2e     # parcours bout en bout (nécessite make up && make seed)
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

`JWT_SIGNING_KEY` signe les jetons citoyens et `PAYMENT_WEBHOOK_SECRET` authentifie les
notifications du prestataire de paiement. Ils doivent être distincts, aléatoires
(au moins 32 octets) et fournis par le coffre de chaque environnement.

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

## Intégration OpenWISP

L'API REST d'OpenWISP ne permet ni d'affecter un groupe RADIUS à un usager, ni de forcer
une déconnexion — or l'activation d'un forfait après paiement dépend du premier, et le
§8.8 exige le second. [ADR-0006](docs/adr/0006-integration-openwisp.md) tranche : une
application d'extension comble les deux manques, **sans fork ni écriture directe en base**.

La maquette est dans [`infra/openwisp-extension/`](infra/openwisp-extension/) et la chaîne
complète a été prouvée sur une instance jetable, un faux NAS recevant réellement les
paquets CoA et Disconnect. Elle doit être durcie avant la phase 5 : droits par
organisation, tests automatisés, version d'OpenWISP épinglée.

Méthode et mesures : [spike OpenWISP](docs/phase0/06-spike-openwisp.md).

## Points ouverts

- Validation matérielle (§6.1) : les passerelles retenues doivent écouter les paquets CoA
  (port 3799) et comprendre `CoovaChilli-Max-Total-Octets`, faute de quoi le quota de
  volume ne s'applique pas côté équipement.
- [Questions bloquantes pour la production](CAHIER_DES_CHARGES_DAKAR_WIFI.md#22-questions-à-valider-avant-la-production) — 19 questions (§22).
