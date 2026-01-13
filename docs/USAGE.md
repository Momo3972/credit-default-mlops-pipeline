# Runbook (USAGE)

Ce runbook permet de reproduire un run local, vérifier l’API, et diagnostiquer les problèmes.

## 1) Lancer la stack complète

```bash
cp .env.example .env
docker compose up --build
```

## 2) Vérifier la santé

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/meta | jq
```

## 3) Faire une prédiction

> 11 features obligatoires.

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data":{"features":[0.1,1.2,0.3,0.0,5.1,2.2,0.8,1.0,0.4,3.2,0.9]}}' | jq
```

## 4) Vérifier monitoring

- Prometheus targets : http://localhost:9090/targets
- Grafana : http://localhost:3000

## 5) Lint/tests/build avant push

```bash
ruff format --check .
ruff check .
pytest -q
docker build -t credit-default-api:local .
```

## 6) Notes Windows / WSL (Zone.Identifier)

Si tu vois des fichiers du type `*.Zone.Identifier`, ce sont des métadonnées Windows.
Tu peux les supprimer avant de pousser :

```bash
find . -name '*:Zone.Identifier' -delete
```
