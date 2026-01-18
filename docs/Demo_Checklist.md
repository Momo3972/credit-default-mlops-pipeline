# Credit Default MLOps – 100% Reproducible Demo Checklist
This checklist is designed to be **fully reproducible** on any machine with: - Docker + Docker Compose - WSL2 (or Linux / macOS) - A web browser It assumes a **clean clone** of the repository. --- 

## 0. Prerequisites (verify once)
bash
docker --version
docker compose version
You should be able to run Docker without sudo inside WSL.

1. Clone the project
bash
Toujours afficher les détails

Copier le code
git clone <YOUR_GITHUB_REPO_URL>
cd credit-default-mlops-pipeline

2. Environment configuration
2.1 Create .env
bash
Toujours afficher les détails

Copier le code
cp .env.example .env

2.2 Verify .env content
bash
Toujours afficher les détails

Copier le code
cat .env
Expected minimum:

env
Toujours afficher les détails

Copier le code
# ===== API / MLflow Registry =====
MODEL_URI=models:/credit-default-model@production

# ===== MLflow Tracking =====
MLFLOW_TRACKING_URI=http://mlflow:5000

# ===== MinIO / S3 =====
MLFLOW_S3_ENDPOINT_URL=http://minio:9000
AWS_ACCESS_KEY_ID=minio
AWS_SECRET_ACCESS_KEY=minio123
AWS_DEFAULT_REGION=us-east-1
AWS_EC2_METADATA_DISABLED=true

# ===== Grafana =====
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin1234!
3. Clean start (mandatory for reproducibility)
bash
Toujours afficher les détails

Copier le code
docker compose down -v
docker compose up -d --build
docker compose ps
Wait until all services are Up.

4. Wait for MLflow to be ready
bash
Toujours afficher les détails

Copier le code
for i in $(seq 1 60); do
  curl -fsS http://localhost:5000/ >/dev/null && echo "MLflow UP" && break
  echo "Waiting for MLflow... ($i/60)"
  sleep 2
done

5. MinIO – create the mlflow bucket
Open browser:

arduino
Toujours afficher les détails

Copier le code
http://localhost:9001
Login:

Access key: minio

Secret key: minio123

Actions:

Click Create Bucket

Name: mlflow

Confirm

6. Train & register the model (one-shot container)
bash
Toujours afficher les détails

Copier le code
docker compose stop api
docker compose run --rm api python /app/train.py
Expected output:

Model registered: credit-default-model

Version created: 1

7. Promote model to production
Open browser:

arduino
Toujours afficher les détails

Copier le code
http://localhost:5000
Steps:

Go to Models

Click credit-default-model

Click Version 1

Add alias:

Alias name: production

Version: 1

8. Restart API with production model
bash
Toujours afficher les détails

Copier le code
docker compose up -d --force-recreate --no-deps api
docker compose ps
Verify env inside container:

bash
Toujours afficher les détails

Copier le code
docker compose exec api sh -lc 'echo "MODEL_URI=$MODEL_URI"'
Expected:

ini
Toujours afficher les détails

Copier le code
MODEL_URI=models:/credit-default-model@production

9. API verification (terminal)
bash
Toujours afficher les détails

Copier le code
curl -fsS http://localhost:8000/health && echo
curl -fsS http://localhost:8000/meta && echo
Expected:

Status OK

Model version = 1

URI = production alias

10. API verification (Swagger)
Open:

bash
Toujours afficher les détails

Copier le code
http://localhost:8000/docs
Actions:

Test /health

Test /meta

Test /predict with sample payload

11. Observability checks
11.1 Prometheus
arduino
Toujours afficher les détails

Copier le code
http://localhost:9090
Status → Targets

credit-default-api must be UP

Metrics endpoint: /metrics

11.2 Grafana
arduino
Toujours afficher les détails

Copier le code
http://localhost:3000
Login:

user: admin

password: admin1234!

Dashboard:

FastAPI / Credit Default – Monitoring

Check RPS, latency p95, error rates

12. Final proof checklist
 MLflow experiment + registered model visible

 MinIO contains artifacts

 API /health = OK

 API /meta shows production model

 Prometheus target UP

 Grafana dashboard populated

13. Panic commands (debug)
bash
Toujours afficher les détails

Copier le code
docker compose ps
docker compose logs --tail=200 api
docker compose logs --tail=200 mlflow
docker compose restart api
End of demo
This checklist is fully reproducible, browser + terminal only, and suitable for:

Live demo

Interview

Teaching

GitHub portfolio

"""

path = "/mnt/data/credit-default-mlops-demo-checklist.md"
with open(path, "w") as f:
f.write(content)

path