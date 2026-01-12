# Credit Default MLOps Pipeline (FastAPI • MLflow • MinIO • Prometheus • Grafana • GitHub Actions)

Pipeline MLOps **de bout en bout** pour la prédiction du défaut de paiement :  
**entraînement → tracking & registry MLflow → API FastAPI dockerisée → monitoring Prometheus/Grafana → CI GitHub Actions (lint/tests/build)**.

> Objectif portfolio : montrer une stack réaliste, reproductible en local, avec des garde-fous (tests, format/lint, build docker), observabilité et un chemin clair vers la prod.

---

## Sommaire
- [Architecture](#architecture)
- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Démarrage rapide](#démarrage-rapide)
- [Entraîner et enregistrer un modèle](#entraîner-et-enregistrer-un-modèle)
- [Servir le modèle via l’API](#servir-le-modèle-via-lapi)
- [Monitoring (Prometheus & Grafana)](#monitoring-prometheus--grafana)
- [Tests & Qualité](#tests--qualité)
- [CI GitHub Actions](#ci-github-actions)
- [Structure du dépôt](#structure-du-dépôt)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Architecture

**Composants**
- **FastAPI** : service de scoring (`/predict`) + endpoints techniques (`/health`, `/meta`, `/metrics`, `/boom`).
- **MLflow Tracking + Model Registry** : suivi d’expériences + versioning du modèle.
- **MinIO (S3)** : stockage des artefacts MLflow.
- **Postgres** : backend store MLflow.
- **Prometheus** : scraping des métriques HTTP exposées par l’API.
- **Grafana** : dashboard prêt à l’emploi via provisioning (datasource UID stable + dashboard JSON chargé au démarrage).
- **GitHub Actions** : `ruff format/check`, `pytest`, build de l’image Docker.

**Flux**
1. `train.py` entraîne un modèle, log en MLflow, et pousse un modèle versionné.
2. Le modèle est référencé par **alias** (ex: `@production`) côté API : `MODEL_URI=models:/credit-default-model@production`.
3. L’API expose des métriques Prometheus (`/metrics`).
4. Prometheus scrape `http://api:8000/metrics`.
5. Grafana affiche RPS, latence p95, ratio 2xx/4xx/5xx.

---

## Fonctionnalités

- ✅ Serving FastAPI dockerisé  
- ✅ Tracking MLflow + artefacts S3 (MinIO) + store Postgres  
- ✅ Monitoring Prometheus/Grafana avec provisioning (reproductible)  
- ✅ Tests unitaires + test d’intégration (marqueur `integration`)  
- ✅ Lint/format Ruff + CI (GitHub Actions)  
- ✅ Endpoint “boom” pour simuler des erreurs 500 et valider l’observabilité

---

## Prérequis

- Docker + Docker Compose
- Python 3.12+ (pour exécuter les scripts localement)
- (Optionnel) `make`

---

## Démarrage rapide

### 1) Cloner & config
```bash
git clone <URL_DU_REPO>
cd credit-default-mlops-pipeline
cp .env.example .env
```

### 2) Lancer la stack principale (MLflow + MinIO + Postgres + API)
```bash
docker compose up -d --build
```

Endpoints:
- API docs : `http://localhost:8000/docs`
- MLflow : `http://localhost:5000`
- MinIO console : `http://localhost:9001`

### 3) Lancer le monitoring (Prometheus + Grafana)
Si vous avez un fichier séparé `docker-compose.monitoring.yml` :
```bash
docker compose -f docker-compose.monitoring.yml up -d
```

Sinon, si monitoring est déjà dans `docker-compose.yml` :
```bash
docker compose up -d
```

Dashboards:
- Grafana : `http://localhost:3000`
- Prometheus : `http://localhost:9090`

---

## Entraîner et enregistrer un modèle

> Selon votre implémentation actuelle, vous avez `train.py` / `evaluate.py`.  
Le principe : définir `MLFLOW_TRACKING_URI`, puis lancer l’entraînement.

Exemple (si `train.py` utilise MLflow via `MLFLOW_TRACKING_URI`) :
```bash
export MLFLOW_TRACKING_URI="http://localhost:5000"
python train.py
```

Ensuite, vérifiez le modèle dans l’UI MLflow (`Models`) et positionnez un alias :
- Alias attendu par l’API : `@production` (recommandé)
- Nom attendu : `credit-default-model` (adapter si besoin)

---

## Servir le modèle via l’API

L’API lit `MODEL_URI` (MLflow Model Registry) au démarrage.

Exemple `.env` / docker-compose :
```env
MODEL_URI=models:/credit-default-model@production
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_S3_ENDPOINT_URL=http://minio:9000
AWS_ACCESS_KEY_ID=minio
AWS_SECRET_ACCESS_KEY=minio123
AWS_DEFAULT_REGION=us-east-1
AWS_EC2_METADATA_DISABLED=true
```

### Tester les endpoints
```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/meta
curl -s http://localhost:8000/metrics | head
```

### Appeler /predict
> Adapter le payload à votre schéma `PredictRequest`.
```bash
curl -s -X POST http://localhost:8000/predict   -H 'Content-Type: application/json'   -d '{"data":{"features":[0,0,0,0,0,0,0,0,0,0]}}'
```

---

## Monitoring (Prometheus & Grafana)

### Prometheus
- Target attendu : `http://api:8000/metrics` (state **UP**)

### Grafana
- Datasource Prometheus provisionnée avec un **UID stable**
- Dashboard JSON chargé automatiquement au démarrage (provider dashboards)

### Test “boom” (pour forcer 500)
```bash
curl -i http://localhost:8000/boom
```
Vous devez voir le ratio 5xx monter.

---

## Tests & Qualité

### Installer dépendances dev
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Lint / format / tests
```bash
ruff format --check .
ruff check .
pytest -q
```

---

## CI GitHub Actions

Workflow :
- `ruff format --check`
- `ruff check`
- `pytest`
- `docker build`

Fichier :
- `.github/workflows/ci.yml`

---

## Structure du dépôt

```
.
├─ api.py
├─ train.py
├─ evaluate.py
├─ predict.py
├─ requirements.txt
├─ requirements-dev.txt
├─ pyproject.toml
├─ pytest.ini
├─ Dockerfile
├─ docker-compose.yml
├─ docker-compose.monitoring.yml
├─ monitoring/
│  ├─ prometheus/
│  └─ grafana/
├─ tests/
│  ├─ conftest.py
│  ├─ test_api.py
│  └─ test_api_integration.py
└─ .github/workflows/ci.yml
```

---

## Troubleshooting

### Prometheus “connection refused” sur `api:8000`
- Vérifier que Prometheus et `api` partagent le même réseau docker.
- Vérifier le job/target dans `prometheus.yml`.
- Vérifier l’endpoint `/metrics`.

### L’API échoue à charger le modèle MLflow
- Vérifier `MODEL_URI`
- Vérifier `MLFLOW_TRACKING_URI` (dans docker: `http://mlflow:5000`)
- Vérifier MinIO (`MLFLOW_S3_ENDPOINT_URL`, `AWS_*`)

### Grafana ne charge pas le dashboard
- Vérifier provisioning dashboards et volume vers `/var/lib/grafana/dashboards`
- Vérifier le JSON (datasource UID)

---

## Roadmap
- Alerting (Alertmanager) + règles
- Tests d’intégration en CI via `docker compose` (job dédié)
- Scan sécurité (Trivy)
- Publication image (GHCR)

---

### Auteur
Projet portfolio : **Momo**
