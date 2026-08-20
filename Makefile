COMPOSE := docker compose -f infra/compose/docker-compose.yml
API := uv run --directory services/core-api
ENVIRONMENT ?= local
MANAGE := ENVIRONMENT=$(ENVIRONMENT) $(API) python manage.py
OPENWISP_DIR := infra/docker-openwisp
OPENWISP_TAG := 25.10.4
OPENWISP_COMPOSE := docker compose -f $(OPENWISP_DIR)/docker-compose.yml --env-file infra/openwisp/.env

.DEFAULT_GOAL := help
.PHONY: help setup up down logs dev migrate makemigrations seed superuser \
        test test-api test-web e2e lint typecheck format openapi check clean \
        openwisp-up openwisp-down test-openwisp

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
	# --build : sans cela, une dépendance ajoutée au pyproject manque dans l'image
	# et l'API échoue à l'import, loin de la cause.
	$(COMPOSE) up -d --build --wait
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
	@if [ "$(ENVIRONMENT)" = "production" ]; then \
	  echo "Refusing to seed demonstration data in production (cahier des charges §1 rule 18)."; \
	  exit 1; \
	fi
	$(MANAGE) seed_demo_data

superuser: ## Crée un compte administrateur Django
	$(MANAGE) createsuperuser

test: test-api test-web ## Lance tous les tests

e2e: ## Parcours bout en bout (nécessite `make up` puis `make seed`)
	pnpm --filter @dakar-wifi/captive-portal build
	pnpm --filter @dakar-wifi/captive-portal test:e2e

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

openwisp-up: ## Instance OpenWISP jetable (hors make up)
	@if [ ! -d "$(OPENWISP_DIR)/.git" ]; then \
	  git clone --depth 1 --branch $(OPENWISP_TAG) https://github.com/openwisp/docker-openwisp.git $(OPENWISP_DIR); \
	fi
	@test -f infra/openwisp/.env || cp infra/openwisp/.env.example infra/openwisp/.env
	@cp infra/openwisp/.env $(OPENWISP_DIR)/.env
	@mkdir -p $(OPENWISP_DIR)/customization/configuration/django
	@cp infra/openwisp-extension/custom_django_settings.py \
	    infra/openwisp-extension/custom_urls.py \
	    $(OPENWISP_DIR)/customization/configuration/django/
	@cp -R infra/openwisp-extension/dakar_radius_ext \
	    $(OPENWISP_DIR)/customization/configuration/django/
	@cp infra/openwisp/seed.py $(OPENWISP_DIR)/customization/configuration/django/
	OPENWISP_VERSION=$(OPENWISP_TAG) $(OPENWISP_COMPOSE) up -d
	@echo "OpenWISP lab: http://localhost:8002"

openwisp-down: ## Arrête l'instance OpenWISP jetable
	@if [ -d "$(OPENWISP_DIR)" ]; then OPENWISP_VERSION=$(OPENWISP_TAG) $(OPENWISP_COMPOSE) down; fi

test-openwisp: openwisp-up ## Tests d'extension + smoke HTTP (pas CI)
	@OPENWISP_VERSION=$(OPENWISP_TAG) $(OPENWISP_COMPOSE) images \
		| awk 'NR > 1 && $$2 ~ /^openwisp\// { found=1; image=$$2 ":" $$3; if (image !~ /:$(OPENWISP_TAG)$$/) bad=1 } END { exit (!found || bad) }'
	OPENWISP_VERSION=$(OPENWISP_TAG) $(OPENWISP_COMPOSE) exec -T api python manage.py test openwisp.configuration.dakar_radius_ext

clean: ## Supprime les services et les volumes (données locales perdues)
	@if [ "$(ENVIRONMENT)" = "production" ]; then \
	  echo "Refusing destructive command in production (cahier des charges §1 rule 18)."; \
	  exit 1; \
	fi
	$(COMPOSE) down -v
