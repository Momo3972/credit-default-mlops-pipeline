# Image du serveur MLflow avec support PostgreSQL (backend store) et MinIO/S3 (artifact store).
# Basée sur l'image officielle mlflow:v2.10.2 — ajoute psycopg2-binary et boto3.
FROM ghcr.io/mlflow/mlflow:v2.10.2

RUN pip install --no-cache-dir \
    psycopg2-binary==2.9.9 \
    boto3==1.34.34
