# ADR-0002 — Stack technique et structure du monorepo

- Statut : Acceptée
- Date : 2026-08-16
- Source : cahier des charges v1.1, §5

## Contexte

Le cahier des charges recommande une stack (Next.js, Django/DRF, PostgreSQL, Redis, Celery)
et une structure de monorepo. Il autorise des ajustements documentés en ADR.

## Décision

Stack conforme au §5, avec les précisions d'outillage suivantes (état des versions
installées localement au 2026-08-16 : Node 25.9, Python 3.14, Docker 29.1) :

| Domaine | Choix | Précision |
|---|---|---|
| Portail + back-office | Next.js (TypeScript, React) | App Router, rendu mobile-first |
| Backend métier | Django + DRF | Python ≥ 3.12 |
| Async | Celery + Redis | broker et cache Redis |
| Base | PostgreSQL 16+ | conteneur en local |
| Gestionnaire JS | **pnpm** (workspaces) | à installer ; espace disque et vitesse ; standard monorepo |
| Orchestration monorepo | pnpm workspaces seuls au départ | Turborepo seulement si le besoin apparaît |
| Gestionnaire Python | **uv** | rapide, lockfile, remplace pip/venv |
| Contrats API | OpenAPI 3.1 via drf-spectacular | client TS généré (`packages/api-client`) |
| Qualité Python | Ruff (lint + format), mypy | |
| Qualité TS | ESLint, Prettier | |
| Tests | Pytest, Vitest, Playwright | |
| Dév local | Docker Compose (`infra/compose/`) | jamais utilisé en production |

La structure de répertoires suit le §5.1 du cahier des charges à l'identique.

## Conséquences

- `pnpm` et `uv` sont des prérequis développeur, documentés dans le README.
- Le client TypeScript est généré depuis le schéma OpenAPI : le schéma est la source
  de vérité du contrat, validé en CI.
- Docker Compose est réservé au développement ; le déploiement production d'OpenWISP
  suit la méthode Ansible officielle (§15.2).

## Alternatives écartées

- **npm workspaces** : fonctionnel mais plus lent, hoisting moins strict.
- **Nx/Turborepo dès le départ** : complexité prématurée pour 2 apps + 1 service.
- **FastAPI au lieu de Django** : DRF apporte l'admin, l'ORM mature, les migrations et
  l'écosystème AAA ; le cahier des charges recommande Django.
