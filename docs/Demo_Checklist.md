# Credit Default MLOps — Checklist de démo reproductible

> **Reproductible à 100 %** sur toute machine disposant de :
> - Docker + Docker Compose v2
> - WSL2 (ou Linux / macOS)
> - Un navigateur web
>
> Temps estimé : **~10 minutes** (hors download des images Docker au premier lancement)

---

## 0. Prérequis

```bash
docker --version          # >= 24.x
docker compose version    # >= 2.x
git --version
```

Assurez-vous de pouvoir lancer Docker sans `sudo` dans WSL.

---

## 1. Cloner le projet

```bash
git clone https://github.com/Momo3972/credit-default-mlops-pipeline.git
cd credit-default-mlops-pipeline
```

---

## 2. Configurer l'environnement

```bash
cp .env.example .env
cat .env   # vérifier les valeurs
```

Valeurs attendues dans `.env` :

```env
MODEL_URI=models:/credit-default-model@production
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_S3_ENDPOINT_URL=http://minio:9000
AWS_ACCESS_KEY_ID=minio
AWS_SECRET_ACCESS_KEY=minio123
AWS_DEFAULT_REGION=us-east-1
AWS_EC2_METADATA_DISABLED=true
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin1234!
```

---

## 3. Démarrage propre (obligatoire pour la reproductibilité)

```bash
docker compose down -v   # supprime les volumes si redémarrage depuis zéro
docker compose up -d --build
docker compose ps        # attendre que tous les services soient "Up (healthy)"
```

---

## 4. Attendre que MLflow soit prêt

```bash
for i in $(seq 1 60); do
  curl -fsS http://localhost:5000/ > /dev/null && echo "MLflow UP ✅" && break
  echo "Attente MLflow... ($i/60)"
  sleep 2
done
```

---

## 5. MinIO — créer le bucket `mlflow`

Ouvrir : **http://localhost:9001**

- Login : `minio` / `minio123`
- Cliquer **Create Bucket** → nommer `mlflow` → confirmer

> Cette étape n'est nécessaire qu'au **premier lancement** (ou après `docker compose down -v`).

---

## 6. Entraîner et comparer les algorithmes

`train.py` entraîne un algorithme à la fois selon `configs/config.yaml`. Lancer 3 runs successifs pour comparer dans MLflow.

```bash
# Run 1 — Logistic Regression (config par défaut)
docker compose run --rm api python /app/train.py

# Run 2 — Random Forest
sed -i 's/type: logistic_regression/type: random_forest/' configs/config.yaml
docker compose run --rm -v $(pwd)/configs:/app/configs api python /app/train.py

# Run 3 — Gradient Boosting
sed -i 's/type: random_forest/type: gradient_boosting/' configs/config.yaml
docker compose run --rm -v $(pwd)/configs:/app/configs api python /app/train.py

# Restaurer config par défaut
sed -i 's/type: gradient_boosting/type: logistic_regression/' configs/config.yaml
```

Résultats obtenus :

| Algorithme | ROC AUC | Recall | F1 |
|---|---|---|---|
| **Gradient Boosting** | **0.8672** | 0.8374 | 0.3012 |
| Random Forest | 0.8463 | 0.8075 | 0.2837 |
| Logistic Regression | 0.8020 | 1.0000 | 0.1254 |

---

## 7. Promouvoir le meilleur modèle en production

Gradient Boosting gagne sur ROC AUC (0.8672) → c'est le modèle à promouvoir.

**Via MLflow UI** (http://localhost:5000) :

→ **Models** → `credit-default-model` → version Gradient Boosting → **Add** (Aliases) → `production` → **Save aliases**

**Via Makefile** :
```bash
make promote
```

---

## 8. Redémarrer l'API avec le modèle de production

```bash
docker compose up -d --force-recreate --no-deps api
docker compose ps
```

Vérifier la variable d'environnement chargée :
```bash
docker compose exec api sh -c 'echo "MODEL_URI=$MODEL_URI"'
# Attendu : MODEL_URI=models:/credit-default-model@production
```

---

## 9. Vérification API (terminal)

```bash
# Santé du service
curl -s http://localhost:8000/health | python3 -m json.tool
# → {"status": "ok", "model_uri": "models:/credit-default-model@production"}

# Métadonnées du modèle
curl -s http://localhost:8000/meta | python3 -m json.tool
# → {"threshold": 0.05, "n_features_expected": 11, "model_version": "1", ...}

# Prédiction — profil risqué → REJECT
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data":{"features":[1,0.8,45,2,0.5,3000,8,1,0,1,3]}}' | python3 -m json.tool

# Prédiction — profil sain → ACCEPT
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data":{"features":[1,0.02,60,0,0.05,10000,2,0,1,0,0]}}' | python3 -m json.tool
```

---

## 10. Vérification API (Swagger UI)

Ouvrir : **http://localhost:8000/docs**

- Tester `GET /health` → `{"status": "ok"}`
- Tester `GET /meta` → `model_version` = 1
- Tester `POST /predict` avec le payload :
  ```json
  {"data": {"features": [1, 0.8, 45, 2, 0.5, 3000, 8, 1, 0, 1, 3]}}
  ```

---

## 11. Observabilité

### Prometheus — targets UP

Ouvrir : **http://localhost:9090/targets**

→ La cible `credit-default-api` doit être **UP** (state: up)

### Grafana — dashboard

Ouvrir : **http://localhost:3000**

- Login : `admin` / `admin1234!`
- Dashboard : **FastAPI / Credit Default — Monitoring**
- Vérifier les panneaux : RPS par handler, Latence p95, Taux 2xx/4xx/5xx

Générer du trafic pour alimenter les métriques :
```bash
for i in {1..30}; do
  curl -s http://localhost:8000/health > /dev/null
  curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"data":{"features":[1,0.8,45,2,0.5,3000,8,1,0,1,3]}}' > /dev/null
done
```

---

## 12. Checklist finale de validation

- [ ] Expérience MLflow visible dans http://localhost:5000
- [ ] Modèle `credit-default-model` enregistré avec alias `@production`
- [ ] MinIO contient les artefacts dans le bucket `mlflow`
- [ ] `GET /health` → `{"status": "ok"}`
- [ ] `GET /meta` → `model_version = 1`, `model_uri` = `...@production`
- [ ] `POST /predict` → réponse JSON avec `probability` + `decision`
- [ ] Prometheus target **UP**
- [ ] Dashboard Grafana alimenté en données

---

## 13. Commandes de debug

```bash
docker compose ps                          # état des services
docker compose logs --tail=100 api         # logs API (chargement modèle...)
docker compose logs --tail=100 mlflow      # logs serveur MLflow
docker compose restart api                 # redémarrage API
make logs                                  # alias : docker compose logs -f api
```

---

*Ce runbook est reproductible en autonomie — terminal + navigateur uniquement.*
*Adapté pour démo en entretien, portfolio GitHub, ou session de formation.*
