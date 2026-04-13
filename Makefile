.PHONY: help install install-dev lint format test test-unit test-integration \
        train evaluate predict build up down restart logs clean promote

# ─── Variables ──────────────────────────────────────────────────────────────
PYTHON       := python3
PIP          := pip
IMAGE_NAME   := credit-default-api
IMAGE_TAG    := latest
COMPOSE      := docker compose
API_URL      ?= http://localhost:8000

# ─── Help ───────────────────────────────────────────────────────────────────
help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Installation ───────────────────────────────────────────────────────────
install: ## Installe les dépendances runtime
	$(PIP) install -r requirements.txt

install-dev: ## Installe les dépendances de développement
	$(PIP) install -r requirements.txt -r requirements-dev.txt

# ─── Qualité code ────────────────────────────────────────────────────────────
lint: ## Lance ruff lint
	ruff check .

format: ## Lance ruff format (vérification)
	ruff format --check .

format-fix: ## Applique le formatage automatique
	ruff format .

# ─── Tests ──────────────────────────────────────────────────────────────────
test: ## Lance tous les tests unitaires
	pytest -q -m "not integration"

test-unit: ## Lance uniquement les tests unitaires
	pytest -q -m "not integration" tests/

test-integration: ## Lance les tests d'intégration (stack Docker requise)
	API_URL=$(API_URL) pytest -q -m integration tests/

test-cov: ## Lance les tests avec couverture de code
	pytest -q -m "not integration" --cov=. --cov-report=term-missing --cov-report=html

# ─── ML Pipeline ────────────────────────────────────────────────────────────
train: ## Entraîne et enregistre le modèle dans MLflow
	$(PYTHON) train.py

evaluate: ## Évalue le modèle enregistré depuis MLflow Registry
	$(PYTHON) evaluate.py

predict: ## Lance les prédictions batch sur cs-test.csv
	$(PYTHON) predict.py

# ─── Docker ──────────────────────────────────────────────────────────────────
build: ## Build l'image Docker de l'API
	docker build \
	  --build-arg GIT_COMMIT=$(shell git rev-parse --short HEAD 2>/dev/null || echo unknown) \
	  -t $(IMAGE_NAME):$(IMAGE_TAG) .

up: ## Lance la stack complète (MLflow + MinIO + Postgres + API + Prometheus + Grafana)
	$(COMPOSE) up -d --build

down: ## Arrête et supprime les conteneurs
	$(COMPOSE) down

down-volumes: ## Arrête et supprime les conteneurs ET les volumes (reset complet)
	$(COMPOSE) down -v

restart: ## Redémarre l'API uniquement
	$(COMPOSE) up -d --force-recreate --no-deps api

logs: ## Affiche les logs de l'API
	$(COMPOSE) logs -f api

logs-all: ## Affiche les logs de tous les services
	$(COMPOSE) logs -f

ps: ## Affiche le statut des conteneurs
	$(COMPOSE) ps

# ─── MLflow / Registry ───────────────────────────────────────────────────────
promote: ## Promeut la dernière version du modèle en alias @production (MLflow CLI)
	@echo "Promotion du modèle credit-default-model → @production"
	$(PYTHON) -c "\
import mlflow, os; \
client = mlflow.tracking.MlflowClient(os.getenv('MLFLOW_TRACKING_URI','http://localhost:5000')); \
versions = client.get_latest_versions('credit-default-model'); \
latest = max(versions, key=lambda v: int(v.version)); \
client.set_registered_model_alias('credit-default-model', 'production', latest.version); \
print(f'Alias @production → version {latest.version}')"

train-in-docker: ## Entraîne le modèle via un conteneur éphémère (stack up requise)
	$(COMPOSE) stop api
	$(COMPOSE) run --rm api python /app/train.py
	$(COMPOSE) up -d --force-recreate --no-deps api

# ─── Sécurité & Audit ────────────────────────────────────────────────────────
security: ## Lance le scan de sécurité (bandit + pip-audit)
	bandit -r . --exclude .venv,tests -ll
	pip-audit

# ─── Nettoyage ───────────────────────────────────────────────────────────────
clean: ## Supprime les caches Python et artefacts locaux
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true

clean-zone: ## Supprime les fichiers Zone.Identifier (Windows/WSL)
	find . -name '*:Zone.Identifier' -delete 2>/dev/null || true

# ─── CI local (simulation) ───────────────────────────────────────────────────
ci: format lint test build ## Simule la CI complète en local
	@echo "✅ CI locale réussie"
