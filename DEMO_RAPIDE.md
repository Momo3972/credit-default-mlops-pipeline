# Guide de démo rapide — Credit Default MLOps Pipeline

Ce guide décrit les étapes pour exécuter le pipeline complet en local, de bout en bout.

**Prérequis :** Docker Desktop + Docker Compose v2 + Git  
**Ports utilisés :** `5000` (MLflow), `8000` (API), `9000/9001` (MinIO), `9090` (Prometheus), `3000` (Grafana)

---

## ÉTAPE 1 — Cloner et configurer

```bash
git clone https://github.com/Momo3972/credit-default-mlops-pipeline.git
cd credit-default-mlops-pipeline
cp .env.example .env
```

> Les valeurs par défaut du `.env` fonctionnent sans modification pour un run local.

---

## ÉTAPE 2 — Démarrer l'infrastructure

```bash
docker compose up -d postgres minio mlflow
docker compose ps   # attendre que les 3 services soient "healthy"
```

| Service         | Port      | Statut attendu |
|-----------------|-----------|----------------|
| mlflow-postgres | 5432      | healthy        |
| mlflow-minio    | 9000/9001 | healthy        |
| mlflow-server   | 5000      | healthy        |

---

## ÉTAPE 3 — Créer le bucket MinIO

Ouvrir **http://localhost:9001** — login : `minio` / `minio123`

→ **Buckets** → **Create Bucket** → nom : `mlflow` → **Create**

> Cette étape n'est nécessaire qu'au premier lancement (ou après `docker compose down -v`).

---

## ÉTAPE 4 — Entraîner et comparer les algorithmes

`train.py` entraîne un algorithme à la fois selon `configs/config.yaml`. Lancer 3 runs pour comparer dans MLflow.

**Run 1 — Logistic Regression (config par défaut) :**
```bash
docker compose run --rm api python /app/train.py
```
```
[logistic_regression] ROC AUC=0.8020 | Recall=1.0000 | F1=0.1254
🏆 Meilleur modèle : logistic_regression (ROC AUC=0.8020)
```

**Run 2 — Random Forest :**
```bash
sed -i 's/type: logistic_regression/type: random_forest/' configs/config.yaml
docker compose run --rm -v $(pwd)/configs:/app/configs api python /app/train.py
```
```
[random_forest] ROC AUC=0.8463 | Recall=0.8075 | F1=0.2837
🏆 Meilleur modèle : random_forest (ROC AUC=0.8463)
```

**Run 3 — Gradient Boosting :**
```bash
sed -i 's/type: random_forest/type: gradient_boosting/' configs/config.yaml
docker compose run --rm -v $(pwd)/configs:/app/configs api python /app/train.py
```
```
[gradient_boosting] ROC AUC=0.8672 | Recall=0.8374 | F1=0.3012
🏆 Meilleur modèle : gradient_boosting (ROC AUC=0.8672)
```

**Restaurer la config par défaut :**
```bash
sed -i 's/type: gradient_boosting/type: logistic_regression/' configs/config.yaml
```

**Résultats comparés :**

| Algorithme | ROC AUC | Recall | F1 |
|---|---|---|---|
| **Gradient Boosting** | **0.8672** | 0.8374 | 0.3012 |
| Random Forest | 0.8463 | 0.8075 | 0.2837 |
| Logistic Regression | 0.8020 | 1.0000 | 0.1254 |

Les 3 runs sont comparables dans MLflow : **http://localhost:5000**

---

## ÉTAPE 5 — Promouvoir le meilleur modèle en production

Gradient Boosting obtient le meilleur ROC AUC → c'est le modèle à promouvoir.

**Via MLflow UI :**

1. Ouvrir **http://localhost:5000**
2. **Models** → `credit-default-model` → version Gradient Boosting
3. **Add** (Aliases) → saisir `production` → **Save aliases**

**Via Makefile :**
```bash
make promote
```

---

## ÉTAPE 6 — Démarrer la stack complète

```bash
docker compose up -d
docker compose ps   # attendre que tous les services soient opérationnels
```

| Service               | Port      | Statut attendu |
|-----------------------|-----------|----------------|
| mlflow-postgres       | 5432      | healthy        |
| mlflow-minio          | 9000/9001 | healthy        |
| mlflow-server         | 5000      | healthy        |
| credit-default-api    | 8000      | healthy        |
| monitoring-prometheus | 9090      | running        |
| monitoring-grafana    | 3000      | running        |

> L'API charge le modèle depuis MLflow au démarrage (~80 secondes).

---

## ÉTAPE 7 — Interfaces disponibles

| Interface       | URL                        | Identifiants       |
|-----------------|----------------------------|--------------------|
| FastAPI Swagger  | http://localhost:8000/docs | —                  |
| MLflow UI        | http://localhost:5000      | —                  |
| MinIO Console    | http://localhost:9001      | minio / minio123   |
| Prometheus       | http://localhost:9090      | —                  |
| Grafana          | http://localhost:3000      | admin / admin1234! |

---

## ÉTAPE 8 — Tester l'API

```bash
# Santé du service
curl -s http://localhost:8000/health | python3 -m json.tool

# Métadonnées du modèle
curl -s http://localhost:8000/meta | python3 -m json.tool

# Prédiction — profil risqué → REJECT
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data":{"features":[1,0.8,45,2,0.5,3000,8,1,0,1,3]}}' | python3 -m json.tool

# Prédiction — profil sain → ACCEPT
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data":{"features":[1,0.02,60,0,0.05,10000,2,0,1,0,0]}}' | python3 -m json.tool
```

Ou depuis Swagger : **http://localhost:8000/docs** → `POST /predict` → **Try it out**

---

## ÉTAPE 9 — Vérifier le monitoring

```bash
# Générer du trafic pour alimenter Grafana
for i in {1..30}; do
  curl -s http://localhost:8000/health > /dev/null
  curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"data":{"features":[1,0.8,45,2,0.5,3000,8,1,0,1,3]}}' > /dev/null
done
```

- **Prometheus targets** : http://localhost:9090/targets → `credit-default-api` doit être **UP**
- **Grafana dashboard** : http://localhost:3000 → *FastAPI / Credit Default — Monitoring*

---

## ÉTAPE 10 — Lancer les tests

```bash
# Tests unitaires via conteneur éphémère (aucune installation locale requise)
docker compose run --rm api python -m pytest /app/tests/test_api.py -v
```

---

## ÉTAPE 11 — Arrêter la stack

```bash
docker compose down          # arrêt simple (volumes conservés)
docker compose down -v       # reset complet (volumes supprimés)
```

---

## Commandes de debug

```bash
docker compose ps                        # état des services
docker compose logs --tail=100 api       # logs API
docker compose logs --tail=50 mlflow     # logs MLflow
docker compose up -d --force-recreate --no-deps api   # redémarrer l'API
make logs                                # logs API en temps réel
```
