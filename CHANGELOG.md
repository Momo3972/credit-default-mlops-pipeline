# Changelog

Tous les changements notables de ce projet sont documentés ici.
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/) — Versioning : [SemVer](https://semver.org/).

---

## [0.2.0] — 2026-04-13

### Ajouté
- Comparaison multi-algorithmes dans `train.py` (LogisticRegression, RandomForest, GradientBoosting)
- Dockerfile multi-stage avec **virtual environment** (`python -m venv /venv`) — pattern recommandé pour les builds multi-stage
- Healthchecks Docker sur tous les services (postgres, minio, mlflow, api) — `condition: service_healthy`
- Réseau Docker explicite `mlops-net` pour isolation des services
- Configuration `pre-commit` (ruff + hooks standards)
- Scan de sécurité dans la CI (`pip-audit` + `bandit`)
- Couverture de code dans la CI (`pytest-cov` + Codecov)
- Cible `make promote` pour promouvoir un modèle en `@production`
- Variables Grafana unifiées via `.env` (plus de mots de passe hardcodés)
- `CHANGELOG.md` et `docs/AUDIT_REPORT.md`

### Modifié
- **Python 3.11** comme version cible (3.12 incompatible avec `mlflow==2.10.2` + `setuptools>=71`)
- `setuptools` épinglé à `>=69,<71` dans `requirements.txt` : `pkg_resources` supprimé dans setuptools 71+, requis par mlflow 2.10.2
- Healthcheck API via `python -c "import urllib.request..."` (curl absent des images slim)
- `evaluate.py` : charge désormais le modèle depuis le MLflow Registry (était ré-entraîné)
- `predict.py` : utilise l'alias `@production` depuis la config (plus de version `/2` hardcodée)
- `api.py` : `THRESHOLD` et `EXPECTED_N_FEATURES` chargés depuis `configs/config.yaml`
- `api.py` : logging Python structuré (plus de `print()`)
- `configs/config.yaml` : alias `@production` (stages `/Production` dépréciés depuis MLflow 2.x)
- `docker-compose.yml` : utilise `infra/mlflow/Dockerfile` + `condition: service_healthy`
- `requirements.txt` : réduit aux dépendances directes (était un freeze complet de 60+ packages)
- `Makefile` : implémenté (était vide — 20+ targets)
- `docs/Demo_Checklist.md` : réécrite proprement (était corrompue avec du code Python brut)
- `pyproject.toml` : `requires-python = ">=3.11"`, `target-version = "py311"`
- CI (`ci.yml`) : Python 3.11

### Supprimé
- `train.py.save` : fichier de sauvegarde éditeur commité par erreur
- `data/predictions.csv` : fichier de sortie généré, retiré du tracking git
- `pytest.ini` : doublon de `[tool.pytest.ini_options]` dans `pyproject.toml`
- `PROJET.docx` : document binaire interne, exclu via `.gitignore`

---

## [0.1.0] — 2026-01-15

### Ajouté
- Pipeline MLOps initial : FastAPI + MLflow + MinIO + PostgreSQL + Prometheus + Grafana
- CI GitHub Actions : ruff + pytest + docker build
- Tests unitaires et d'intégration
- Documentation : ARCHITECTURE.md, MONITORING.md, USAGE.md
- Dashboard Grafana provisionné automatiquement
