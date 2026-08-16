COMPOSE := docker compose -f infra/compose/docker-compose.yml
API := uv run --directory services/core-api
MANAGE := ENVIRONMENT=local $(API) python manage.py

.DEFAULT_GOAL := help
.PHONY: help setup up down logs dev migrate makemigrations seed superuser \
        test test-api test-web lint typecheck format openapi check clean

help: ## Affiche cette aide
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.env:
	@cp .env.example .env
	@echo "Fichier .env créé depuis .env.example (valeurs fictives)."

setup: .env ## Installe toutes les dépendances (JS et Python)
	pnpm install
	uv sync --directory services/core-api

up: .env ## Démarre la base, le cache, l'API et le worker
	$(COMPOSE) up -d --wait
	$(MAKE) migrate

down: ## Arrête les services (les données sont conservées)
	$(COMPOSE) down

logs: ## Suit les journaux des services
	$(COMPOSE) logs -f

dev: up ## Démarre tout puis les deux front-ends en mode développement
	pnpm dev

migrate: ## Applique les migrations
	$(MANAGE) migrate

makemigrations: ## Génère les migrations
	$(MANAGE) makemigrations

seed: ## Charge les données de démonstration (refusé en production)
	$(MANAGE) seed_demo_data

superuser: ## Crée un compte administrateur Django
	$(MANAGE) createsuperuser

test: test-api test-web ## Lance tous les tests

test-api: .env ## Tests backend (pytest, sur PostgreSQL réel)
	$(COMPOSE) up -d --wait db redis
	$(API) pytest

test-web: ## Tests front-end (vitest)
	pnpm test

lint: ## Lint backend et front-end
	$(API) ruff check .
	$(API) ruff format --check .
	pnpm lint

typecheck: ## Vérification des types (mypy et tsc)
	$(API) mypy .
	pnpm typecheck

format: ## Formate le code
	$(API) ruff format .
	$(API) ruff check --fix .
	pnpm exec prettier --write .

openapi: ## Régénère le schéma OpenAPI et le client TypeScript
	$(MANAGE) spectacular --format openapi --file ../../docs/api/openapi.yaml
	pnpm api-client:generate

check: lint typecheck test ## Reproduit localement les contrôles de la CI

clean: ## Supprime les services et les volumes (données locales perdues)
	$(COMPOSE) down -v
