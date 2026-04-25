# Runbook d'utilisation

Ce runbook permet de reproduire un run local complet, tester l'API et diagnostiquer les problèmes courants.

---

## 1. Démarrer la stack complète

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps   # attendre que tous les services soient "healthy" ou "running"
```

> La stack comprend 6 services : `postgres`, `minio`, `mlflow`, `api`, `prometheus`, `grafana`

---

## 2. Créer le bucket MinIO (première fois uniquement)

Ouvrir **http://localhost:9001** - login : `minioadmin` / `minioadmin123`

→ **Buckets** -> **Create Bucket** -> nom : `mlflow` -> **Create**

---

## 3. Entraîner et comparer les algorithmes

`train.py` entraîne un algorithme à la fois (défini dans `configs/config.yaml`). Lancer 3 runs pour comparer dans MLflow :

```bash
# Run 1 - Logistic Regression (défaut)
docker compose run --rm api python /app/train.py

# Run 2 - Random Forest
sed -i 's/type: logistic_regression/type: random_forest/' configs/config.yaml
docker compose run --rm -v $(pwd)/configs:/app/configs api python /app/train.py

# Run 3 - Gradient Boosting
sed -i 's/type: random_forest/type: gradient_boosting/' configs/config.yaml
docker compose run --rm -v $(pwd)/configs:/app/configs api python /app/train.py

# Restaurer config par défaut
sed -i 's/type: gradient_boosting/type: logistic_regression/' configs/config.yaml
```

Résultats obtenus (dataset Give Me Some Credit, 150k clients) :

| Algorithme | ROC AUC | Recall | F1 |
|---|---|---|---|
| **Gradient Boosting** | **0.8672** | 0.8374 | 0.3012 |
| Random Forest | 0.8463 | 0.8075 | 0.2837 |
| Logistic Regression | 0.8020 | 1.0000 | 0.1254 |

Les 3 runs sont visibles et comparables dans MLflow : http://localhost:5000

---

## 4. Promouvoir le meilleur modèle en production

Gradient Boosting obtient le meilleur ROC AUC -> c'est le modèle à promouvoir.

**Via MLflow UI** : http://localhost:5000 -> **Models** -> `credit-default-model` -> version Gradient Boosting -> **Add** (Aliases) -> `production` -> **Save aliases**

**Via Makefile** :
```bash
make promote
```

---

## 5. Vérifier la santé de l'API

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
# {"status": "ok", "model_uri": "models:/credit-default-model@production"}

curl -s http://localhost:8000/meta | python3 -m json.tool
# {"model_uri": "...", "threshold": 0.05, "n_features_expected": 11, "git_commit": "...", "model_version": "1"}
```

---

## 6. Faire une prédiction

Le payload attend **11 features** dans cet ordre exact :

| # | Feature | Exemple risqué | Exemple sain |
|---|---|---|---|
| 1 | index ligne (CSV) | `1` | `1` |
| 2 | RevolvingUtilizationOfUnsecuredLines | `0.8` | `0.02` |
| 3 | age | `45` | `60` |
| 4 | NumberOfTime30-59DaysPastDueNotWorse | `2` | `0` |
| 5 | DebtRatio | `0.5` | `0.05` |
| 6 | MonthlyIncome | `3000` | `10000` |
| 7 | NumberOfOpenCreditLinesAndLoans | `8` | `2` |
| 8 | NumberOfTimes90DaysLate | `1` | `0` |
| 9 | NumberRealEstateLoansOrLines | `0` | `1` |
| 10 | NumberOfTime60-89DaysPastDueNotWorse | `1` | `0` |
| 11 | NumberOfDependents | `3` | `0` |

```bash
# Profil risqué → REJECT
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data":{"features":[1,0.8,45,2,0.5,3000,8,1,0,1,3]}}' | python3 -m json.tool

# Profil sain → ACCEPT
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data":{"features":[1,0.02,60,0,0.05,10000,2,0,1,0,0]}}' | python3 -m json.tool
```

Réponse attendue :
```json
{
  "probability": 0.453,
  "decision": "REJECT",
  "threshold": 0.05,
  "model_uri": "models:/credit-default-model@production"
}
```

---

## 7. Vérifier le monitoring

```bash
# Prometheus - targets
open http://localhost:9090/targets   # "credit-default-api" doit être UP

# Grafana - dashboard
open http://localhost:3000           # admin / admin1234!
# Dashboard : "FastAPI / Credit Default - Monitoring"

# Générer du trafic pour alimenter les métriques
for i in {1..20}; do
  curl -s http://localhost:8000/health > /dev/null
  curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"data":{"features":[1,0.8,45,2,0.5,3000,8,1,0,1,3]}}' > /dev/null
done
```

---

## 8. Qualité du code - vérifications avant push

```bash
ruff format --check .   # vérification du format
ruff check .            # lint
pytest -q               # tests unitaires
docker build -t credit-default-api:local .   # validation du build
```

Ou via Makefile :
```bash
make lint
make test
make build
```

---

## 9. Commandes de debug

```bash
docker compose ps                    # état de tous les services
docker compose logs --tail=50 api    # logs de l'API (erreurs de chargement modèle…)
docker compose logs --tail=50 mlflow # logs du serveur MLflow
docker compose restart api           # redémarrer l'API sans toucher les autres services
make logs                            # alias : docker compose logs -f api
```

### Problème courant : API en erreur au démarrage

Si l'API démarre avant que le modèle soit promu `@production`, elle log une erreur mais reste en attente. Vérifier :
1. Que le modèle est enregistré dans MLflow Registry (http://localhost:5000)
2. Que l'alias `@production` est bien assigné
3. Redémarrer : `docker compose restart api`

---

## 10. Notes WSL2 / Windows

Si des fichiers `*.Zone.Identifier` apparaissent dans le repo (métadonnées Windows) :

```bash
find . -name '*:Zone.Identifier' -delete
```

Ces fichiers sont déjà ignorés via `.gitignore`.
